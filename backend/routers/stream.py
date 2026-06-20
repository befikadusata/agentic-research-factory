from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from uuid import UUID
import json
from utils.redis_client import get_redis_client

router = APIRouter()
LOG_CHANNEL_PREFIX = "run_log:"

@router.get("/{run_id}/stream")
async def stream_run(run_id: UUID):
    rid = str(run_id)
    redis_client = await get_redis_client()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{LOG_CHANNEL_PREFIX}{rid}")

    async def event_generator():
        try:
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
