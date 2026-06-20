import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_protected_routes_unauthorized():
    protected_paths = [
        ("/runs", "GET"),
        ("/runs", "POST"),
        ("/upload", "POST"),
        ("/runs/11111111-1111-1111-1111-111111111111/approve", "POST"),
        ("/runs/11111111-1111-1111-1111-111111111111/output/pdf", "GET"),
        ("/runs/11111111-1111-1111-1111-111111111111/output/md", "GET"),
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for path, method in protected_paths:
            if method == "GET":
                response = await ac.get(path)
            elif method == "POST":
                body = {}
                if path == "/runs":
                    body = {"topic": "test topic", "format": "report"}
                response = await ac.post(path, json=body)
            
            # Should be 401 Unauthorized if auth is working
            assert response.status_code == 401
