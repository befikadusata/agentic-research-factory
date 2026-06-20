import asyncio
import json
import re
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
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
    redis_client = await get_redis_client()
    event = {"type": event_type, "data": data}
    await redis_client.publish(f"{LOG_CHANNEL_PREFIX}{run_id}", json.dumps(event))

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

            collection_name = f"run_{rid.replace('-', '_')}"
            context_docs = ""
            if run.doc_paths:
                from services.pdf_service import parse_pdfs
                from tools.rag import ingest_documents
                chunks = await parse_pdfs(run.doc_paths)
                if chunks:
                    ingest_documents(chunks, collection_name=collection_name)
                    context_docs = f"Documents ingested into collection: {collection_name}."

            vertical_config = get_vertical(run.vertical)
            execution_brief = build_execution_brief(run.topic, run.vertical, run.vertical_inputs or {})

            from agents.crew import supervisor
            def _step_cb(step):
                # Note: this callback is tricky in distributed environments.
                # Simplification: Log to DB or use emit here if safe.
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
            
            # STAGE 3: Final Approval
            user_feedback = await _wait_for_hitl(rid, RunStatus.awaiting_final_approval, "hitl_required", run.final_output)

            await _set_status(run, RunStatus.complete, db)
            await emit(rid, "complete", {"output": run.final_output[:500]})

    except Exception as e:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if run: await _set_status(run, RunStatus.failed, db)
        error_msg = str(e)
        await emit(rid, "error", {"message": f"Run failed: {error_msg[:200]}"})
        raise

async def approve_hitl(run_id: str, instruction: str | None = None):
    redis_client = await get_redis_client()
    if instruction:
        await redis_client.set(f"{HITL_INSTRUCTION_KEY}{run_id}", instruction)
    # Set the signal key
    await redis_client.set(f"{HITL_SIGNAL_KEY}{run_id}", "approved")
