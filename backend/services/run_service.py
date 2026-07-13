import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from database import AsyncSessionLocal
from models import Run, RunStatus
from logger import logger
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, before_sleep_log
from configs.verticals import build_execution_brief, get_vertical
from utils.redis_client import get_redis_client, LOG_CHANNEL_PREFIX, HITL_INSTRUCTION_KEY
from utils.cost_tracker import log_cost
from utils.pricing import calculate_cost
from services.eval_service import evaluate_output
from services.monitor_service import finalize_monitored_run

LLM_STAGE_TIMEOUT_SEC = 300

# run.metrics sub-key holding the few graph-internal fields that aren't already
# their own Run column (plan_output, retry_count). They must survive across the
# separate Celery tasks that now run each stage, since the in-memory LangGraph
# checkpoint does not (Celery recycles the worker child after every task).
_GRAPH_KEY = "_graph_state"


async def emit(run_id: str, event_type: str, data: dict):
    entry = {"type": event_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()}
    try:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, UUID(run_id))
            if run is not None:
                logs = list(run.logs or [])
                logs.append(entry)
                run.logs = logs
                flag_modified(run, "logs")
                await db.commit()
    except Exception:
        pass  # DB persistence is best-effort; Redis publish is authoritative for live streaming
    redis_client = await get_redis_client()
    await redis_client.publish(f"{LOG_CHANNEL_PREFIX}{run_id}", json.dumps({"type": event_type, "data": data}))


async def _log_token_usages(run_id: str, token_usages: list):
    for usage in token_usages:
        try:
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            cost = calculate_cost(usage.get("model", ""), prompt_tokens, completion_tokens)
            async with AsyncSessionLocal() as db:
                await log_cost(
                    db, run_id,
                    usage["agent_name"],
                    prompt_tokens,
                    completion_tokens,
                    cost,
                )
        except Exception:
            pass


async def _set_status(run: Run, status: RunStatus, db: AsyncSession):
    if status == RunStatus.failed and run.status != RunStatus.failed:
        run.failed_at_status = run.status
    run.status = status
    run.updated_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()


async def _claim_status(run_id: UUID, expected: RunStatus, new: RunStatus) -> bool:
    """Atomically move a run from `expected` to `new`, returning True only if
    THIS caller made the transition. Guards each segment against a duplicate or
    stale resume: a run advances past a gate exactly once, so a double approval
    (or an autonomous dispatch racing a manual one) can't skip the next gate —
    the second claim finds the run already moved and no-ops."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_update(Run)
            .where(Run.id == run_id, Run.status == expected)
            .values(status=new, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()
        return result.rowcount > 0


async def _invoke_supervisor_with_retry(supervisor, state: dict | None, config: dict, recursion_limit: int = 25):
    """Run (or resume) the graph up to its next interrupt point or END.

    `state=None` resumes an in-progress thread (`config["configurable"]["thread_id"]`)
    from its last checkpoint instead of starting a fresh graph run.

    On a *retry* we deliberately resume from the checkpoint (input=None) rather
    than re-sending the original `state`. LangGraph checkpoints after every
    super-step, so when a mid-graph node fails the nodes that already ran are
    durably recorded; replaying the original input would restart from START and
    overwrite those checkpointed channels with the stale entry values (e.g.
    plan_output -> "" from the reconstructed state), throwing away completed work
    and re-billing it. Resuming re-runs only the failed super-step. (M1)
    """
    call_config = {**config, "recursion_limit": recursion_limit}
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            invoke_input = state if attempt.retry_state.attempt_number == 1 else None
            call = asyncio.to_thread(supervisor.invoke, invoke_input, call_config)
            return await asyncio.wait_for(call, timeout=LLM_STAGE_TIMEOUT_SEC)


async def _resume_graph_at(supervisor, entry_state: dict, config: dict, recursion_limit: int = 25):
    """Re-enter the graph at `entry_state["_resume_from"]` in a fresh process.

    Because that node sits behind interrupt_before, the first invoke only loads
    the reconstructed state and pauses *before* the node; invoke(None) then runs
    it onward to the next interrupt or END. Returns the resulting state.
    """
    await _invoke_supervisor_with_retry(supervisor, entry_state, config, recursion_limit)
    return await _invoke_supervisor_with_retry(supervisor, None, config, recursion_limit)


def _dispatch_resume(run_id: str, approved_gate: str | None):
    """Queue the next pipeline segment for `run_id` in a fresh Celery task.

    This is the seam that lets a run durably pause: the current task returns
    (releasing the worker) and the next segment is picked up by a new child.
    `approved_gate` is the awaiting_* status that was just approved (None for the
    initial start), so the resuming task advances exactly that gate and can
    detect (via _claim_status) that a stale/duplicate resume refers to a gate the
    run has already left. Isolated in one function so tests can drive the state
    machine synchronously.
    """
    from celery_app import execute_run_task
    execute_run_task.delay(run_id, approved_gate)


def _is_autonomous(run: Run) -> bool:
    # Monitor-spawned runs have no human at the approval gates, so they advance
    # themselves. Ordinary runs wait for an operator to POST /approve.
    return run.monitor_id is not None


def _read_graph_stash(run: Run) -> dict:
    return dict((run.metrics or {}).get(_GRAPH_KEY, {}))


def _make_step_cb(rid: str, loop: asyncio.AbstractEventLoop):
    # emit "log" type with {agent, message, ts} so the frontend AgentLog populates.
    def _step_cb(step):
        agent_role = (
            step.agent.role
            if hasattr(step, "agent") and hasattr(step.agent, "role")
            else "system"
        )
        data = {
            "agent":   agent_role,
            "message": str(step)[:300],
            "ts":      datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run_coroutine_threadsafe(emit(rid, "log", data), loop)
    return _step_cb


def _graph_config(rid: str, loop: asyncio.AbstractEventLoop) -> dict:
    # step_callback rides in `configurable` (per-call, never checkpointed) rather
    # than in state, since a live function reference isn't serializable. thread_id
    # is the run id; each segment runs in a fresh child so the in-memory
    # checkpointer starts empty and there's no cross-run collision.
    return {"configurable": {"thread_id": rid, "step_callback": _make_step_cb(rid, loop)}}


async def _pop_instruction(rid: str) -> str:
    """Read and clear the operator's approval instruction (the feedback they
    typed when approving the prior stage). Empty for autonomous runs."""
    redis_client = await get_redis_client()
    instruction = await redis_client.get(f"{HITL_INSTRUCTION_KEY}{rid}")
    if instruction is not None:
        await redis_client.delete(f"{HITL_INSTRUCTION_KEY}{rid}")
    return instruction or ""


async def _enter_gate(run_id: UUID, status: RunStatus, summary: str):
    """Durably pause the run at a human-in-the-loop gate.

    Persists the `awaiting_*` status (the resume point), notifies the UI, and
    then either auto-advances (autonomous/monitor runs) or returns so the worker
    is freed until an operator approves. Crucially it does NOT block the worker
    waiting for a human — that was the old design's fatal flaw.
    """
    rid = str(run_id)
    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        if run is None:
            return
        autonomous = _is_autonomous(run)
        await _set_status(run, status, db)
    await emit(rid, "hitl_required", {"stage": status.value, "summary": (summary or "")[:2000]})
    if autonomous:
        # No human at the gate — advance to the next segment immediately, in a
        # fresh task, so monitored runs actually run to completion (and reach
        # finalize_monitored_run) instead of hanging on an approval that never comes.
        _dispatch_resume(rid, status.value)


# ── segment dispatcher ────────────────────────────────────────────────────────

async def execute_run(run_id: UUID, approved_gate: str | None = None):
    """Run exactly one pipeline segment, then return (releasing the Celery
    worker). The run advances across separate tasks: a fresh run starts with
    `approved_gate=None`; approving a HITL gate re-enqueues this with that gate's
    status, and the matching segment runs — but only if the run is still parked
    at that gate (each segment claims its gate atomically), so a stale or
    duplicate approval can't skip ahead.
    """
    rid = str(run_id)
    log = logger.bind(run_id=rid)

    try:
        if approved_gate is None:
            log.info("starting_run")
            await _run_start_segment(run_id)
        elif approved_gate == RunStatus.awaiting_research_approval.value:
            await _run_analyse_segment(run_id)
        elif approved_gate == RunStatus.awaiting_analysis_approval.value:
            await _run_write_segment(run_id)
        elif approved_gate == RunStatus.awaiting_final_approval.value:
            await _finalize(run_id)
        else:
            log.info("execute_run_noop", approved_gate=approved_gate)
    except Exception as e:
        log.exception("run_failed")
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            if run_obj:
                run_obj.error_message = str(e)[:500]
                await _set_status(run_obj, RunStatus.failed, db)
        error_msg = str(e)
        await emit(rid, "error", {"message": f"Run failed: {error_msg[:200]}"})
        # Re-raise so Celery records the task FAILED — but NOT the original
        # exception: tenacity's RetryError embeds a concurrent.futures.Future,
        # which is unpickleable and crashes Celery's result backend. Raise a
        # plain RuntimeError and drop the unpickleable cause chain (`from None`).
        raise RuntimeError(f"Run {rid} failed: {error_msg[:500]}") from None


# ── segment 1: start (research/plan or lead-intel single pass) ────────────────

async def _run_start_segment(run_id: UUID):
    rid = str(run_id)
    log = logger.bind(run_id=rid)
    loop = asyncio.get_running_loop()

    # Claim the run so a duplicate initial dispatch can't start it twice.
    if not await _claim_status(run_id, RunStatus.pending, RunStatus.researching):
        logger.bind(run_id=rid).info("start_segment_already_claimed")
        return

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        if not run:
            return
        workspace_id    = run.workspace_id
        doc_paths       = list(run.doc_paths or [])
        vertical        = run.vertical
        vertical_inputs = dict(run.vertical_inputs or {})
        topic           = run.topic
        run_format      = run.format

    collection_name = (
        f"workspace_{workspace_id}" if workspace_id
        else f"run_{rid.replace('-', '_')}"
    )

    # ── Wait for referenced documents to be ingested ──────────────────────────
    context_docs = ""
    if doc_paths:
        from models import Document, DocumentStatus
        from sqlalchemy import select as sa_select

        doc_ids = [UUID(d) for d in doc_paths if d]
        POLL_INTERVAL = 5
        POLL_TIMEOUT  = 300
        elapsed = 0

        while elapsed < POLL_TIMEOUT:
            # Fresh session each iteration — kills the SQLAlchemy identity-map
            # caching that previously prevented status updates from being seen.
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    sa_select(Document).where(Document.id.in_(doc_ids))
                )
                docs    = result.scalars().all()
                failed  = [d for d in docs if d.status == DocumentStatus.failed]
                pending = [d for d in docs if d.status == DocumentStatus.pending]

            if failed:
                names     = ", ".join(d.filename for d in failed)
                error_msg = f"Document ingestion failed for: {names}"
                async with AsyncSessionLocal() as db:
                    run_obj = await db.get(Run, run_id)
                    if run_obj:
                        run_obj.error_message = error_msg
                        await _set_status(run_obj, RunStatus.failed, db)
                await emit(rid, "error", {"message": error_msg})
                return

            if not pending:
                context_docs = f"Documents ingested into collection: {collection_name}."
                break

            await emit(rid, "status", {"status": "waiting_for_documents", "pending": len(pending)})
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
        else:
            error_msg = "Timed out waiting for document ingestion"
            async with AsyncSessionLocal() as db:
                run_obj = await db.get(Run, run_id)
                if run_obj:
                    run_obj.error_message = error_msg
                    await _set_status(run_obj, RunStatus.failed, db)
            await emit(rid, "error", {"message": error_msg})
            return

    vertical_config = get_vertical(vertical)
    execution_brief = build_execution_brief(topic, vertical, vertical_inputs)
    task_type       = vertical_config["task_type"] if vertical_config else "research_report"

    from agents.crew import supervisor
    from tools.rag import extract_citations

    initial_state = {
        "topic":           execution_brief,
        "vertical":        vertical,
        "task_type":       task_type,
        "context_docs":    context_docs,
        "collection_name": collection_name,
        "output_format":   run_format,
        "workspace_id":    str(workspace_id) if workspace_id else "",
        "research_output": "",
        "plan_output":     "",
        "analysis_output": "",
        "final_output":    "",
        "review_output":   "",
        "retry_count":     0,
        "user_feedback":   "",
        "_resume_from":    "",
        "token_usages":    [],
    }
    config = _graph_config(rid, loop)

    # status is already `researching` from the claim above.
    await emit(rid, "status", {"status": "researching"})
    await emit(rid, "agent_start", {"stage": "research"})

    if task_type == "lead_intel":
        # Single pass → END, then a single (final) approval gate.
        final_state = await _invoke_supervisor_with_retry(
            supervisor, initial_state, config, recursion_limit=15
        )
        await emit(rid, "agent_end", {"stage": "research"})
        await _log_token_usages(rid, final_state.get("token_usages", []))

        final_output    = final_state.get("final_output", "")
        final_citations = extract_citations(final_output or "")
        eval_scores     = await _safe_eval(final_output, final_output, topic, log)

        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.final_output = final_output
            run_obj.metrics = {
                **(run_obj.metrics or {}),
                "citations": final_citations,
                "eval_scores": eval_scores,
            }
            flag_modified(run_obj, "metrics")
            await db.commit()

        await asyncio.to_thread(supervisor.checkpointer.delete_thread, rid)
        await _enter_gate(run_id, RunStatus.awaiting_final_approval, final_output)
        return

    # research_report: plan → research → pause before analyse (research approval).
    state = await _invoke_supervisor_with_retry(
        supervisor, initial_state, config, recursion_limit=25
    )
    await emit(rid, "agent_end", {"stage": "research"})
    await _log_token_usages(rid, state.get("token_usages", []))

    research_output = state.get("research_output", "")
    citations = extract_citations(research_output or "")
    async with AsyncSessionLocal() as db:
        run_obj = await db.get(Run, run_id)
        run_obj.research_output = research_output
        run_obj.metrics = {
            **(run_obj.metrics or {}),
            "citations": citations,
            # plan_output/retry_count aren't Run columns but the analyse segment
            # (a separate task, fresh process) needs them to rebuild graph state.
            _GRAPH_KEY: {"plan_output": state.get("plan_output", ""), "retry_count": 0},
        }
        flag_modified(run_obj, "metrics")
        await db.commit()

    await asyncio.to_thread(supervisor.checkpointer.delete_thread, rid)
    await _enter_gate(run_id, RunStatus.awaiting_research_approval, research_output)


# ── segment 2: analyse (analyse → review → pause) ─────────────────────────────

async def _run_analyse_segment(run_id: UUID):
    rid = str(run_id)
    log = logger.bind(run_id=rid)
    loop = asyncio.get_running_loop()

    # Only proceed if the run is still parked at the research gate — a stale or
    # duplicate approval that refers to a gate already passed is a no-op.
    if not await _claim_status(run_id, RunStatus.awaiting_research_approval, RunStatus.analyzing):
        log.info("analyse_segment_stale_resume")
        return

    user_feedback = await _pop_instruction(rid)

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        if not run:
            return
        research_output = run.research_output or ""
        vertical        = run.vertical
        vertical_inputs = dict(run.vertical_inputs or {})
        topic           = run.topic
        run_format      = run.format
        workspace_id    = run.workspace_id
        stash           = _read_graph_stash(run)

    execution_brief = build_execution_brief(topic, vertical, vertical_inputs)

    from agents.crew import supervisor

    entry_state = {
        "topic":           execution_brief,
        "vertical":        vertical,
        "task_type":       "research_report",
        "context_docs":    "",
        "collection_name": None,
        "output_format":   run_format,
        "workspace_id":    str(workspace_id) if workspace_id else "",
        "research_output": research_output,
        "plan_output":     stash.get("plan_output", ""),
        "analysis_output": "",
        "final_output":    "",
        "review_output":   "",
        "retry_count":     stash.get("retry_count", 0),
        "user_feedback":   user_feedback,
        "_resume_from":    "analyse",
        "token_usages":    [],
    }
    config = _graph_config(rid, loop)

    # status is already `analyzing` from the claim above.
    await emit(rid, "status", {"status": "analyzing"})
    await emit(rid, "agent_start", {"stage": "analysis"})

    state = await _resume_graph_at(supervisor, entry_state, config, recursion_limit=25)
    await emit(rid, "agent_end", {"stage": "analysis"})
    await _log_token_usages(rid, state.get("token_usages", []))

    snapshot  = await asyncio.to_thread(supervisor.get_state, config)
    next_node = snapshot.next[0] if snapshot.next else None
    retry_count = state.get("retry_count", stash.get("retry_count", 0))

    if next_node == "analyse":
        # review FAILed → research was re-run and we paused before analyse again.
        # Surface the retried research for a fresh approval instead of silently
        # redoing already-approved work.
        research_output = state.get("research_output", research_output)
        citations = _extract(research_output)
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.research_output = research_output
            run_obj.metrics = {
                **(run_obj.metrics or {}),
                "citations": citations,
                _GRAPH_KEY: {"plan_output": stash.get("plan_output", ""), "retry_count": retry_count},
            }
            flag_modified(run_obj, "metrics")
            await db.commit()
        await asyncio.to_thread(supervisor.checkpointer.delete_thread, rid)
        await _enter_gate(run_id, RunStatus.awaiting_research_approval, research_output)
        return

    # next_node == "write" (review PASSed, or retry cap hit → proceed anyway):
    # analysis is done, pause for analysis approval.
    if next_node != "write":
        log.warning("unexpected_graph_pause", next_node=next_node)

    analysis_output = state.get("analysis_output", "")
    async with AsyncSessionLocal() as db:
        run_obj = await db.get(Run, run_id)
        run_obj.analysis_output = analysis_output
        run_obj.metrics = {
            **(run_obj.metrics or {}),
            _GRAPH_KEY: {"plan_output": stash.get("plan_output", ""), "retry_count": retry_count},
        }
        flag_modified(run_obj, "metrics")
        await db.commit()
    await asyncio.to_thread(supervisor.checkpointer.delete_thread, rid)
    await _enter_gate(run_id, RunStatus.awaiting_analysis_approval, analysis_output)


# ── segment 3: write (write → edit → END) ─────────────────────────────────────

async def _run_write_segment(run_id: UUID):
    rid = str(run_id)
    log = logger.bind(run_id=rid)
    loop = asyncio.get_running_loop()

    if not await _claim_status(run_id, RunStatus.awaiting_analysis_approval, RunStatus.writing):
        log.info("write_segment_stale_resume")
        return

    user_feedback = await _pop_instruction(rid)

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        if not run:
            return
        research_output = run.research_output or ""
        analysis_output = run.analysis_output or ""
        vertical        = run.vertical
        vertical_inputs = dict(run.vertical_inputs or {})
        topic           = run.topic
        run_format      = run.format
        workspace_id    = run.workspace_id
        stash           = _read_graph_stash(run)

    execution_brief = build_execution_brief(topic, vertical, vertical_inputs)

    from agents.crew import supervisor

    entry_state = {
        "topic":           execution_brief,
        "vertical":        vertical,
        "task_type":       "research_report",
        "context_docs":    "",
        "collection_name": None,
        "output_format":   run_format,
        "workspace_id":    str(workspace_id) if workspace_id else "",
        "research_output": research_output,
        "plan_output":     stash.get("plan_output", ""),
        "analysis_output": analysis_output,
        "final_output":    "",
        "review_output":   "",
        "retry_count":     stash.get("retry_count", 0),
        "user_feedback":   user_feedback,
        "_resume_from":    "write",
        "token_usages":    [],
    }
    config = _graph_config(rid, loop)

    # status is already `writing` from the claim above.
    await emit(rid, "status", {"status": "writing"})
    await emit(rid, "agent_start", {"stage": "writing"})

    state = await _resume_graph_at(supervisor, entry_state, config, recursion_limit=25)
    await emit(rid, "agent_end", {"stage": "writing"})
    await _log_token_usages(rid, state.get("token_usages", []))

    final_output    = state.get("final_output", "")
    eval_scores     = await _safe_eval(final_output, research_output, topic, log)
    final_citations = _extract(final_output)

    async with AsyncSessionLocal() as db:
        run_obj = await db.get(Run, run_id)
        run_obj.final_output = final_output
        existing = (run_obj.metrics or {}).get("citations", [])
        merged   = {(c["source"], c["page"]): c for c in existing + final_citations}
        run_obj.metrics = {
            **(run_obj.metrics or {}),
            "citations": list(merged.values()),
            "eval_scores": eval_scores,
        }
        flag_modified(run_obj, "metrics")
        await db.commit()

    await asyncio.to_thread(supervisor.checkpointer.delete_thread, rid)
    await _enter_gate(run_id, RunStatus.awaiting_final_approval, final_output)


# ── segment 4: finalize (final approval granted → complete) ───────────────────

async def _finalize(run_id: UUID):
    rid = str(run_id)
    # Claim final approval → complete atomically so a duplicate approval doesn't
    # run finalize_monitored_run (and any alert) twice.
    if not await _claim_status(run_id, RunStatus.awaiting_final_approval, RunStatus.complete):
        logger.bind(run_id=rid).info("finalize_stale_resume")
        return

    async with AsyncSessionLocal() as db:
        run_obj = await db.get(Run, run_id)
        if not run_obj:
            return
        final_output = run_obj.final_output or ""
        latency_sec = (datetime.now(timezone.utc) - run_obj.created_at).total_seconds()
        run_obj.metrics = {**(run_obj.metrics or {}), "latency_sec": latency_sec}
        flag_modified(run_obj, "metrics")
        run_obj.updated_at = datetime.now(timezone.utc)
        db.add(run_obj)
        await db.commit()

    await emit(rid, "complete", {"final_output": final_output[:500]})
    await finalize_monitored_run(run_id)


# ── small helpers ─────────────────────────────────────────────────────────────

def _extract(text: str) -> list:
    from tools.rag import extract_citations
    return extract_citations(text or "")


async def _safe_eval(content: str, research: str, topic: str, log) -> dict:
    try:
        return await evaluate_output(content=content, research=research, topic=topic)
    except Exception as e:
        log.warning("eval_failed", error=str(e))
        return {}


# ── HITL approval ─────────────────────────────────────────────────────────────

async def approve_hitl(run_id: str, instruction: str | None, gate: str):
    """Operator approved the stage `gate` (an awaiting_* status the API layer has
    already validated the run is parked at). Stash any feedback for the next
    segment to pick up, then queue that segment — the run resumes in a fresh
    worker child rather than unblocking a task that was holding the worker. The
    resume is tagged with `gate` so the segment it triggers only advances that
    gate (a stale/duplicate approval no-ops via _claim_status)."""
    if instruction:
        redis_client = await get_redis_client()
        await redis_client.set(f"{HITL_INSTRUCTION_KEY}{run_id}", instruction, ex=7200)
    _dispatch_resume(run_id, gate)
