import asyncio
import json
import re
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from database import AsyncSessionLocal
from models import Run, RunStatus
from logger import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from configs.verticals import build_execution_brief, get_vertical
from utils.redis_client import get_redis_client, LOG_CHANNEL_PREFIX, HITL_SIGNAL_KEY, HITL_INSTRUCTION_KEY

LLM_STAGE_TIMEOUT_SEC = 300


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

async def _set_status(run: Run, status: RunStatus, db: AsyncSession):
    run.status = status
    run.updated_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _invoke_supervisor_with_retry(supervisor, state: dict, recursion_limit: int = 25):
    config = {"recursion_limit": recursion_limit}
    call = asyncio.to_thread(supervisor.invoke, state, config)
    return await asyncio.wait_for(call, timeout=LLM_STAGE_TIMEOUT_SEC)

async def _wait_for_hitl(run_id: str, status: RunStatus, emit_event: str, summary: str):
    async with AsyncSessionLocal() as db:
        run = await db.get(Run, UUID(run_id))  # Fix 2: explicit UUID cast (was plain string)
        if run:
            await _set_status(run, status, db)
            await emit(run_id, emit_event, {"stage": status.value, "summary": summary[:2000]})

    redis_client = await get_redis_client()
    signal_key = f"{HITL_SIGNAL_KEY}{run_id}"

    try:
        for _ in range(360):  # 30 mins (360 * 5s)
            if await redis_client.exists(signal_key):
                break
            await asyncio.sleep(5)
        else:
            raise asyncio.TimeoutError
    except asyncio.TimeoutError:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, UUID(run_id))  # Fix 2: explicit UUID cast
            if run:
                await _set_status(run, RunStatus.failed, db)
        await emit(run_id, "error", {"message": f"HITL stage {status} timed out after 30 minutes."})
        raise asyncio.TimeoutError

    instruction = await redis_client.get(f"{HITL_INSTRUCTION_KEY}{run_id}")
    await redis_client.delete(signal_key)
    await redis_client.delete(f"{HITL_INSTRUCTION_KEY}{run_id}")
    return instruction or ""

async def execute_run(run_id: UUID):
    rid = str(run_id)
    logger.info("starting_run", run_id=rid)

    # Fix 6: capture running loop here (async context), before any to_thread calls
    loop = asyncio.get_running_loop()

    try:
        # ── Read initial run config (short-lived session) ──────────────────────
        # Fix 3: no longer hold session across the entire run
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

        # ── Wait for referenced documents to be ingested ───────────────────────
        context_docs = ""
        if doc_paths:
            from models import Document, DocumentStatus
            from sqlalchemy import select as sa_select

            doc_ids = [UUID(d) for d in doc_paths if d]
            POLL_INTERVAL = 5
            POLL_TIMEOUT  = 300
            elapsed = 0

            while elapsed < POLL_TIMEOUT:
                # Fix 1: fresh session each iteration — kills the SQLAlchemy identity-map
                # caching that previously prevented status updates from being seen
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

        vertical_config  = get_vertical(vertical)
        execution_brief  = build_execution_brief(topic, vertical, vertical_inputs)

        from agents.crew import supervisor
        from tools.rag import extract_citations

        # Fix 4+6: emit "log" type with {agent, message, ts} so AgentLog populates
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

        task_type      = vertical_config["task_type"] if vertical_config else "research_report"
        run_start_time = datetime.now(timezone.utc)
        user_feedback  = ""

        # ── RESEARCH ─────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            await _set_status(run_obj, RunStatus.researching, db)
        await emit(rid, "status", {"status": "researching"})
        await emit(rid, "agent_start", {"stage": "research"})
        research_state = await _invoke_supervisor_with_retry(supervisor, {
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
            "step_callback":   _step_cb,
            "user_feedback":   user_feedback,
        }, recursion_limit=15)
        await emit(rid, "agent_end", {"stage": "research"})

        research_output = research_state.get("research_output", "")
        citations       = extract_citations(research_output or "")
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.research_output = research_output
            run_obj.metrics = {**(run_obj.metrics or {}), "citations": citations}
            flag_modified(run_obj, "metrics")
            await db.commit()

        # STAGE 1: Research Approval — no session held during wait
        user_feedback = await _wait_for_hitl(
            rid, RunStatus.awaiting_research_approval, "hitl_required", research_output
        )

        # ── ANALYSIS ─────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            await _set_status(run_obj, RunStatus.analyzing, db)
        await emit(rid, "status", {"status": "analyzing"})
        await emit(rid, "agent_start", {"stage": "analysis"})
        analysis_state = await _invoke_supervisor_with_retry(supervisor, {
            **research_state, "analysis_output": "", "user_feedback": user_feedback
        }, recursion_limit=15)
        await emit(rid, "agent_end", {"stage": "analysis"})

        analysis_output = analysis_state.get("analysis_output", "")
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.analysis_output = analysis_output
            await db.commit()

        # STAGE 2: Analysis Approval — no session held during wait
        user_feedback = await _wait_for_hitl(
            rid, RunStatus.awaiting_analysis_approval, "hitl_required", analysis_output
        )

        # ── WRITING ───────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            await _set_status(run_obj, RunStatus.writing, db)
        await emit(rid, "status", {"status": "writing"})
        await emit(rid, "agent_start", {"stage": "writing"})
        final_state = await _invoke_supervisor_with_retry(supervisor, {
            **analysis_state, "final_output": "", "user_feedback": user_feedback
        }, recursion_limit=25)
        await emit(rid, "agent_end", {"stage": "writing"})

        final_output = final_state.get("final_output", "")

        # Merge final-output citations (dedup by source+page)
        final_citations = extract_citations(final_output or "")
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.final_output = final_output
            existing = (run_obj.metrics or {}).get("citations", [])
            merged   = {(c["source"], c["page"]): c for c in existing + final_citations}
            run_obj.metrics = {**(run_obj.metrics or {}), "citations": list(merged.values())}
            flag_modified(run_obj, "metrics")
            await db.commit()

        # STAGE 3: Final Approval — no session held during wait
        user_feedback = await _wait_for_hitl(
            rid, RunStatus.awaiting_final_approval, "hitl_required", final_output
        )

        latency_sec = (datetime.now(timezone.utc) - run_start_time).total_seconds()
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            run_obj.metrics = {**(run_obj.metrics or {}), "latency_sec": latency_sec}
            flag_modified(run_obj, "metrics")
            await _set_status(run_obj, RunStatus.complete, db)

        # Fix 9: key was "output", now "final_output" to match SSEEvent type
        await emit(rid, "complete", {"final_output": final_output[:500]})

    except Exception as e:
        async with AsyncSessionLocal() as db:
            run_obj = await db.get(Run, run_id)
            if run_obj:
                run_obj.error_message = str(e)[:500]
                await _set_status(run_obj, RunStatus.failed, db)
        error_msg = str(e)
        await emit(rid, "error", {"message": f"Run failed: {error_msg[:200]}"})
        raise

async def approve_hitl(run_id: str, instruction: str | None = None):
    redis_client = await get_redis_client()
    if instruction:
        await redis_client.set(f"{HITL_INSTRUCTION_KEY}{run_id}", instruction, ex=7200)
    await redis_client.set(f"{HITL_SIGNAL_KEY}{run_id}", "approved", ex=7200)
