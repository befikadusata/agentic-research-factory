import pytest
import asyncio
import json
import uuid
from utils.redis_client import init_redis_pool, LOG_CHANNEL_PREFIX, HITL_INSTRUCTION_KEY
from services.run_service import emit, approve_hitl
import services.run_service as run_service

@pytest.fixture
async def redis_client():
    client = init_redis_pool()
    yield client

@pytest.mark.asyncio
async def test_redis_emit_and_stream(redis_client):
    run_id = str(uuid.uuid4())
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{LOG_CHANNEL_PREFIX}{run_id}")

    await emit(run_id, "test_event", {"message": "hello"})

    message = None
    for _ in range(10):
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message:
            break
        await asyncio.sleep(0.1)

    assert message is not None
    data = json.loads(message["data"])
    assert data["type"] == "test_event"
    assert data["data"]["message"] == "hello"

    await pubsub.unsubscribe()
    await pubsub.aclose()

@pytest.mark.asyncio
async def test_redis_hitl_signaling(redis_client, monkeypatch):
    run_id = str(uuid.uuid4())
    gate = "awaiting_research_approval"

    # approve_hitl (a) stashes the operator's feedback for the next segment and
    # (b) queues that segment via _dispatch_resume tagged with the approved gate,
    # which is why _dispatch_resume is the patch target here.
    dispatched = []
    monkeypatch.setattr(run_service, "_dispatch_resume", lambda rid, g: dispatched.append((rid, g)))

    instruction = "Please refine the search."
    await approve_hitl(run_id, instruction, gate)

    assert dispatched == [(run_id, gate)]
    assert await redis_client.get(f"{HITL_INSTRUCTION_KEY}{run_id}") == instruction

    await redis_client.delete(f"{HITL_INSTRUCTION_KEY}{run_id}")

