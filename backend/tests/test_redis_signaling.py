import pytest
import asyncio
import json
import uuid
from utils.redis_client import get_redis_client
from services.run_service import emit, approve_hitl, HITL_SIGNAL_KEY, LOG_CHANNEL_PREFIX

@pytest.fixture
async def redis_client():
    client = await get_redis_client()
    yield client
    await client.aclose()

@pytest.mark.asyncio
async def test_redis_emit_and_stream(redis_client):
    run_id = str(uuid.uuid4())
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{LOG_CHANNEL_PREFIX}{run_id}")

    # Simulate emit from "worker"
    await emit(run_id, "test_event", {"message": "hello"})

    # Verify received by "streamer"
    # Wait for message with timeout
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
async def test_redis_hitl_signaling(redis_client):
    run_id = str(uuid.uuid4())
    
    # Simulate API approval
    instruction = "Please refine the search."
    await approve_hitl(run_id, instruction)

    # Verify signal set
    assert await redis_client.exists(f"{HITL_SIGNAL_KEY}{run_id}")
    
    # Clean up
    await redis_client.delete(f"{HITL_SIGNAL_KEY}{run_id}")
    await redis_client.delete(f"run_hitl_instr:{run_id}")

