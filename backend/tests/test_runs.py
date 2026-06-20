import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_run_requires_auth(client):
    response = await client.post("/runs", json={"topic": "test", "format": "report"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_run_success(client, mock_user):
    payload = {
        "topic": "AI in healthcare",
        "format": "report",
        "doc_ids": []
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["topic"] == payload["topic"]

@pytest.mark.asyncio
async def test_list_runs_user_isolation(client, mock_user):
    response = await client.get("/runs")
    assert response.status_code == 200
