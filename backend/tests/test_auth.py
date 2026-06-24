import pytest
from httpx import AsyncClient, ASGITransport
from main import app

FAKE_UUID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_protected_routes_unauthorized():
    protected_paths = [
        ("/runs", "GET"),
        ("/runs", "POST"),
        ("/upload", "POST"),
        (f"/runs/{FAKE_UUID}/approve", "POST"),
        (f"/runs/{FAKE_UUID}/output/pdf", "GET"),
        (f"/runs/{FAKE_UUID}/output/md", "GET"),
        (f"/runs/{FAKE_UUID}/stream", "GET"),
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for path, method in protected_paths:
            if method == "GET":
                response = await ac.get(path)
            else:
                body = {"topic": "test topic", "format": "report"} if path == "/runs" else {}
                response = await ac.post(path, json=body)

            assert response.status_code == 401, f"{method} {path} expected 401, got {response.status_code}"
