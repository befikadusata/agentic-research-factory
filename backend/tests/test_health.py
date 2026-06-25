import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture(autouse=True)
async def reset_db_engine():
    # The shared database.py engine pools asyncpg connections that are bound to
    # a specific event loop. With per-function event loops in tests, any connections
    # from a previous test become stale. Disposing before each test forces fresh ones.
    from database import engine
    await engine.dispose()
    yield


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
