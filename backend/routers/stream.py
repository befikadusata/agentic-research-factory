from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json
from database import get_db, AsyncSessionLocal
from models import Run, RunStatus
from utils.redis_client import get_redis_client, LOG_CHANNEL_PREFIX
from auth import get_current_user, assert_run_access

router = APIRouter()

TERMINAL_STATUSES = {RunStatus.complete, RunStatus.failed}


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    await assert_run_access(run, user_id, db)

    rid = str(run_id)
    redis_client = await get_redis_client()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{LOG_CHANNEL_PREFIX}{rid}")

    async def event_generator():
        try:
            # Fix 5: re-fetch status AFTER subscribe to close the TOCTOU gap.
            # If the run already finished before we subscribed, no future publish
            # will arrive — yield a synthetic terminal event and close immediately.
            async with AsyncSessionLocal() as fresh_db:
                current = await fresh_db.get(Run, run_id)
            if current and current.status in TERMINAL_STATUSES:
                evt_type = "complete" if current.status == RunStatus.complete else "error"
                yield {"data": json.dumps({"type": evt_type, "data": {}})}
                return

            async for message in pubsub.listen():
                if message["type"] == "message":
                    event = json.loads(message["data"])
                    yield {"data": json.dumps(event)}
                    if event.get("type") in ("complete", "error"):
                        break
        finally:
            await pubsub.unsubscribe(f"{LOG_CHANNEL_PREFIX}{rid}")
            await pubsub.close()

    return EventSourceResponse(event_generator())
