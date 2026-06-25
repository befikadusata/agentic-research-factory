import asyncio
import json
import pytest
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from models import Run, RunStatus


@pytest.fixture(autouse=True)
async def reset_sse_app_status():
    # sse_starlette stores AppStatus.should_exit_event as a class-level asyncio.Event.
    # With per-function event loops (asyncio_default_fixture_loop_scope=function),
    # the event becomes bound to a stale loop after the first test. Reset it each time.
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = asyncio.Event()
    yield


def _mock_async_session(run):
    """Return a factory that, when called, acts as AsyncSessionLocal() returning a mock db."""
    @asynccontextmanager
    async def _factory():
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=run)
        yield mock_db
    return _factory


async def _make_run(db, user_id: str, status: RunStatus = RunStatus.pending) -> Run:
    run = Run(id=uuid.uuid4(), user_id=user_id, topic="t", format="report", status=status, doc_paths=[])
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


def _make_redis_mock():
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    return mock_redis, mock_pubsub


@pytest.mark.asyncio
async def test_stream_requires_auth(client):
    r = await client.get(f"/runs/{uuid.uuid4()}/stream")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stream_returns_404_for_other_users_run(client, mock_user, db_session):
    run = await _make_run(db_session, "other-user-xyz")
    r = await client.get(f"/runs/{run.id}/stream")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_stream_closes_immediately_for_complete_run(client, mock_user, db_session):
    run = await _make_run(db_session, mock_user, RunStatus.complete)
    mock_redis, _ = _make_redis_mock()

    with patch("routers.stream.get_redis_client", AsyncMock(return_value=mock_redis)), \
         patch("routers.stream.AsyncSessionLocal", _mock_async_session(run)):
        async with client.stream("GET", f"/runs/{run.id}/stream") as response:
            assert response.status_code == 200
            body = await response.aread()

    events = _parse_sse(body.decode())
    assert len(events) == 1
    assert events[0]["type"] == "complete"


@pytest.mark.asyncio
async def test_stream_closes_immediately_for_failed_run(client, mock_user, db_session):
    run = await _make_run(db_session, mock_user, RunStatus.failed)
    mock_redis, _ = _make_redis_mock()

    with patch("routers.stream.get_redis_client", AsyncMock(return_value=mock_redis)), \
         patch("routers.stream.AsyncSessionLocal", _mock_async_session(run)):
        async with client.stream("GET", f"/runs/{run.id}/stream") as response:
            assert response.status_code == 200
            body = await response.aread()

    events = _parse_sse(body.decode())
    assert len(events) == 1
    assert events[0]["type"] == "error"


@pytest.mark.asyncio
async def test_stream_emits_log_then_complete_from_pubsub(client, mock_user, db_session):
    run = await _make_run(db_session, mock_user, RunStatus.researching)
    mock_redis, mock_pubsub = _make_redis_mock()

    log_msg = json.dumps({"type": "log", "data": {"msg": "working"}})
    complete_msg = json.dumps({"type": "complete", "data": {}})

    # Mock get_message to return messages in sequence then None (signals exhaustion).
    # The heartbeat loop will stop when it sees a terminal event.
    _messages = [
        {"type": "message", "data": log_msg},
        {"type": "message", "data": complete_msg},
    ]
    _call_count = 0

    async def _fake_get_message(ignore_subscribe_messages=True, timeout=0):
        nonlocal _call_count
        if _call_count < len(_messages):
            msg = _messages[_call_count]
            _call_count += 1
            return msg
        return None

    mock_pubsub.get_message = _fake_get_message

    # Patch AsyncSessionLocal to return a non-terminal status so the generator
    # doesn't short-circuit and instead consumes the mocked pubsub messages.
    with patch("routers.stream.get_redis_client", AsyncMock(return_value=mock_redis)), \
         patch("routers.stream.AsyncSessionLocal", _mock_async_session(run)):
        async with client.stream("GET", f"/runs/{run.id}/stream") as response:
            assert response.status_code == 200
            body = await response.aread()

    events = [e for e in _parse_sse(body.decode()) if e != "heartbeat"]
    assert len(events) == 2
    assert events[0]["type"] == "log"
    assert events[1]["type"] == "complete"


def _parse_sse(text: str) -> list:
    """Extract JSON payloads from SSE data lines."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return events
