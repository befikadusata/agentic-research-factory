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
from utils.redis_client import get_redis_client

LLM_STAGE_TIMEOUT_SEC = 300

# Pub/Sub channel prefix for SSE logs
LOG_CHANNEL_PREFIX = "run_log:"
# Key prefix for HITL signals and instructions
HITL_SIGNAL_KEY = "run_hitl_signal:"
HITL_INSTRUCTION_KEY = "run_hitl_instr:"

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
        run = await db.get(Run, run_id)
        if run:
            await _set_status(run, status, db)
            await emit(run_id, emit_event, {"research_summary": summary[:2000]})

    redis_client = await get_redis_client()
    signal_key = f"{HITL_SIGNAL_KEY}{run_id}"
    
    try:
        # Poll/Wait for signal (using blpop or key existence)
        # Using a simple key-based approach for now
        for _ in range(360): # 30 mins (360 * 5s)
            if await redis_client.exists(signal_key):
                break
            await asyncio.sleep(5)
        else:
            raise asyncio.TimeoutError
    except asyncio.TimeoutError:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if run:
                await _set_status(run, RunStatus.failed, db)
        await emit(run_id, "error", {"message": f"HITL stage {status} timed out after 30 minutes."})
        raise asyncio.TimeoutError
    
    # Retrieve instructions
    instruction = await redis_client.get(f"{HITL_INSTRUCTION_KEY}{run_id}")
    # Cleanup
    await redis_client.delete(signal_key)
    await redis_client.delete(f"{HITL_INSTRUCTION_KEY}{run_id}")
    
    return instruction or ""

async def execute_run(run_id: UUID):
    rid = str(run_id)
    logger.info("starting_run", run_id=rid)
    user_feedback = ""

    try:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if not run: return

            # ── Resolve collection name ──
            if run.workspace_id:
                collection_name = f"workspace_{run.workspace_id}"
            else:
                collection_name = f"run_{rid.replace('-', '_')}"

            # ── Wait for referenced documents to be ingested ──
            context_docs = ""
            if run.doc_paths:
                from models import Document, DocumentStatus
                from sqlalchemy import select as sa_select
                from uuid import UUID as _UUID

                doc_ids = [_UUID(d) for d in run.doc_paths if d]
                POLL_INTERVAL = 5
                POLL_TIMEOUT = 300
                elapsed = 0

                while elapsed < POLL_TIMEOUT:
                    result = await db.execute(
                        sa_select(Document).where(Document.id.in_(doc_ids))
                    )
                    docs = result.scalars().all()

                    failed = [d for d in docs if d.status == DocumentStatus.failed]
                    if failed:
                        names = ", ".join(d.filename for d in failed)
                        run.error_message = f"Document ingestion failed for: {names}"
                        await _set_status(run, RunStatus.failed, db)
                        await emit(rid, "error", {"message": run.error_message})
                        return

                    pending = [d for d in docs if d.status == DocumentStatus.pending]
                    if not pending:
                        context_docs = f"Documents ingested into collection: {collection_name}."
                        break

                    await emit(rid, "status", {"status": "waiting_for_documents", "pending": len(pending)})
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL
                    # Expire cached objects so next iteration re-fetches from DB
                    await db.execute(sa_select(Document).where(Document.id.in_(doc_ids)))
                else:
                    run.error_message = "Timed out waiting for document ingestion"
                    await _set_status(run, RunStatus.failed, db)
                    await emit(rid, "error", {"message": run.error_message})
                    return

            vertical_config = get_vertical(run.vertical)
            execution_brief = build_execution_brief(run.topic, run.vertical, run.vertical_inputs or {})

            from agents.crew import supervisor
            from tools.rag import extract_citations
            def _step_cb(step):
                pass

            task_type = vertical_config["task_type"] if vertical_config else ("lead_intel" if run.format == "lead_intel" else "research_report")

            # ── RESEARCH ──
            await _set_status(run, RunStatus.researching, db)
            await emit(rid, "status", {"status": "researching"})
            research_state = await _invoke_supervisor_with_retry(supervisor, {
                "topic": execution_brief, "vertical": run.vertical, "task_type": task_type,
                "context_docs": context_docs, "collection_name": collection_name, "output_format": run.format,
                "research_output": "", "plan_output": "", "step_callback": _step_cb,
                "user_feedback": user_feedback
            }, recursion_limit=15)

            run.research_output = research_state.get("research_output", "")

            # Persist citations from research output
            citations = extract_citations(run.research_output or "")
            run.metrics = {**(run.metrics or {}), "citations": citations}
            flag_modified(run, "metrics")

            # STAGE 1: Research Approval
            user_feedback = await _wait_for_hitl(rid, RunStatus.awaiting_research_approval, "hitl_required", run.research_output)

            # ── ANALYSIS ──
            await _set_status(run, RunStatus.analyzing, db)
            await emit(rid, "status", {"status": "analyzing"})
            analysis_state = await _invoke_supervisor_with_retry(supervisor, {
                **research_state, "analysis_output": "", "user_feedback": user_feedback
            }, recursion_limit=15)

            run.analysis_output = analysis_state.get("analysis_output", "")

            # STAGE 2: Analysis Approval
            user_feedback = await _wait_for_hitl(rid, RunStatus.awaiting_analysis_approval, "hitl_required", run.analysis_output)

            # ── WRITING ──
            await _set_status(run, RunStatus.writing, db)
            await emit(rid, "status", {"status": "writing"})
            final_state = await _invoke_supervisor_with_retry(supervisor, {
                **analysis_state, "final_output": "", "user_feedback": user_feedback
            }, recursion_limit=25)

            run.final_output = final_state.get("final_output", "")

            # Merge final output citations (dedup by source+page)
            final_citations = extract_citations(run.final_output or "")
            existing = (run.metrics or {}).get("citations", [])
            merged = {(c["source"], c["page"]): c for c in existing + final_citations}
            run.metrics = {**(run.metrics or {}), "citations": list(merged.values())}
            flag_modified(run, "metrics")

            # STAGE 3: Final Approval
            user_feedback = await _wait_for_hitl(rid, RunStatus.awaiting_final_approval, "hitl_required", run.final_output)

            await _set_status(run, RunStatus.complete, db)
            await emit(rid, "complete", {"output": run.final_output[:500]})

    except Exception as e:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if run:
                run.error_message = str(e)[:500]
                await _set_status(run, RunStatus.failed, db)
        error_msg = str(e)
        await emit(rid, "error", {"message": f"Run failed: {error_msg[:200]}"})
        raise

async def approve_hitl(run_id: str, instruction: str | None = None):
    redis_client = await get_redis_client()
    if instruction:
        await redis_client.set(f"{HITL_INSTRUCTION_KEY}{run_id}", instruction)
    # Set the signal key
    await redis_client.set(f"{HITL_SIGNAL_KEY}{run_id}", "approved")
