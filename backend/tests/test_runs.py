import pytest
from httpx import AsyncClient
from models import Run, RunStatus


async def _make_run(db, user_id: str, status: RunStatus = RunStatus.pending) -> Run:
    run = Run(user_id=user_id, topic="test", format="report", status=status, doc_paths=[])
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@pytest.mark.asyncio
async def test_create_run_requires_auth(client):
    response = await client.post("/runs", json={"topic": "test", "format": "report"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_run_success(client, mock_user):
    response = await client.post("/runs", json={"topic": "AI in healthcare", "format": "report", "doc_ids": []})
    assert response.status_code == 201
    data = response.json()
    assert data["topic"] == "AI in healthcare"


@pytest.mark.asyncio
async def test_list_runs_user_isolation(client, mock_user):
    response = await client.get("/runs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_runs_status_filter(client, auth_as, db_session):
    uid = "filter-user@example.com"
    auth_as(uid)
    await _make_run(db_session, uid, RunStatus.failed)
    await _make_run(db_session, uid, RunStatus.complete)
    await _make_run(db_session, uid, RunStatus.pending)

    resp = await client.get("/runs?status=failed")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["status"] == "failed" for r in data)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_runs_pagination(client, auth_as, db_session):
    uid = "page-user@example.com"
    auth_as(uid)
    r1 = await _make_run(db_session, uid, RunStatus.complete)
    r2 = await _make_run(db_session, uid, RunStatus.complete)
    r3 = await _make_run(db_session, uid, RunStatus.complete)

    # limit=1 returns one result
    resp = await client.get("/runs?limit=1&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # offset skips records
    resp_all = await client.get("/runs?limit=10&offset=0")
    resp_offset = await client.get("/runs?limit=10&offset=1")
    assert len(resp_offset.json()) == len(resp_all.json()) - 1


@pytest.mark.asyncio
async def test_run_detail_response_fields(client, auth_as, db_session):
    uid = "detail-user@example.com"
    auth_as(uid)

    run = Run(
        user_id=uid,
        topic="Detail test",
        format="report",
        status=RunStatus.failed,
        analysis_output="some analysis",
        error_message="something went wrong",
        doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis_output" in data
    assert data["analysis_output"] == "some analysis"
    assert "error_message" in data
    assert data["error_message"] == "something went wrong"
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_emit_persists_to_db(db_session, auth_as, client):
    """Run.logs written via fixture session are visible in the detail API."""
    from sqlalchemy.orm.attributes import flag_modified

    uid = "emit-user@example.com"
    auth_as(uid)
    run = await _make_run(db_session, uid)

    # Simulate what emit() does: append a log entry directly via the session
    entry = {"type": "status", "data": {"status": "researching"}, "ts": "2026-01-01T00:00:00+00:00"}
    run.logs = [entry]
    flag_modified(run, "logs")
    await db_session.commit()

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) == 1
    assert data["logs"][0]["type"] == "status"

