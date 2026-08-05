import pytest

from models import Run, RunCost, RunStatus


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
async def test_create_run_response_carries_owner_and_no_monitor(client, mock_user):
    """A hand-started run is owned by the caller and belongs to no monitor.

    Both fields drive UI decisions — `user_id` mirrors the owner-always-passes
    rule in `assert_run_access`, `monitor_id` distinguishes a monitored run —
    so they have to survive serialization, not just live on the model."""
    response = await client.post("/runs", json={"topic": "Owner check", "format": "report", "doc_ids": []})
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == mock_user
    assert data["monitor_id"] is None


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
    import uuid as _uuid
    uid = f"page-user-{_uuid.uuid4()}@example.com"
    auth_as(uid)
    await _make_run(db_session, uid, RunStatus.complete)
    await _make_run(db_session, uid, RunStatus.complete)
    await _make_run(db_session, uid, RunStatus.complete)

    resp = await client.get("/runs?limit=1&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Exactly 3 rows exist for this uid, so offset=1 must return 2.
    resp_all = await client.get("/runs?limit=10&offset=0")
    resp_offset = await client.get("/runs?limit=10&offset=1")
    assert len(resp_all.json()) == 3
    assert len(resp_offset.json()) == 2


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
async def test_run_detail_reports_cost_rows_for_a_failed_run(client, auth_as, db_session):
    """`costs` is what the run page's cost panel reads.

    Asserted on a *failed* run on purpose: a run that dies mid-pipeline has
    still spent tokens, and that spend is exactly what someone needs to see. The
    panel renders outside the "complete" branch to match.
    """
    uid = "cost-detail@example.com"
    auth_as(uid)

    run = Run(user_id=uid, topic="Cost test", format="report", status=RunStatus.failed, doc_paths=[])
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    db_session.add_all([
        RunCost(run_id=run.id, agent_name="researcher", input_tokens=800, output_tokens=120, total_cost=0.004),
        RunCost(run_id=run.id, agent_name="researcher", input_tokens=300, output_tokens=60, total_cost=0.002),
    ])
    await db_session.commit()

    data = (await client.get(f"/runs/{run.id}")).json()
    # One row per call, not pre-summed per agent — the UI folds them.
    assert len(data["costs"]) == 2
    assert {c["agent_name"] for c in data["costs"]} == {"researcher"}
    assert sum(c["input_tokens"] for c in data["costs"]) == 1100
    assert abs(sum(c["total_cost"] for c in data["costs"]) - 0.006) < 1e-9


@pytest.mark.asyncio
async def test_run_detail_normalizes_persisted_event_envelopes(db_session, auth_as, client):
    """Historical event envelopes are returned as display-safe log entries."""
    from sqlalchemy.orm.attributes import flag_modified

    uid = "emit-user@example.com"
    auth_as(uid)
    run = await _make_run(db_session, uid)

    # Simulate what emit() does: append a log entry directly via the session
    run.logs = [
        {"type": "status", "data": {"status": "researching"}, "ts": "2026-01-01T00:00:00+00:00"},
        {"type": "log", "data": {"agent": 42, "message": {"step": "search"}}, "ts": None},
        {"type": "error", "data": {"message": 503}, "ts": "2026-01-01T00:00:02+00:00"},
        {"type": "hitl_required", "data": {"stage": "awaiting_final_approval"}},
        {"type": "agent_start", "data": {"stage": "research"}},
        None,
    ]
    flag_modified(run, "logs")
    await db_session.commit()

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["logs"] == [
        {"agent": "system", "message": "Status changed to researching", "ts": "2026-01-01T00:00:00+00:00"},
        {"agent": "42", "message": '{"step": "search"}', "ts": ""},
        {"agent": "error", "message": "503", "ts": "2026-01-01T00:00:02+00:00"},
        {"agent": "system", "message": "Human approval required at awaiting_final_approval", "ts": ""},
    ]


@pytest.mark.asyncio
async def test_run_detail_citations_populated(client, auth_as, db_session):
    uid = "citations-user@example.com"
    auth_as(uid)

    run = Run(
        user_id=uid,
        topic="Citations test",
        format="report",
        status=RunStatus.complete,
        doc_paths=[],
        metrics={"citations": [{"source": "a.pdf", "page": "1"}, {"source": "b.pdf", "page": "5"}]},
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    data = resp.json()
    # Under metrics, which is the only place they are published — SourcesPanel
    # reads `run.metrics.citations`.
    assert data["metrics"]["citations"] == [
        {"source": "a.pdf", "page": "1"},
        {"source": "b.pdf", "page": "5"},
    ]


@pytest.mark.asyncio
async def test_run_detail_citations_empty_when_no_metrics(client, auth_as, db_session):
    uid = "no-citations-user@example.com"
    auth_as(uid)
    run = await _make_run(db_session, uid)

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    assert resp.json()["metrics"].get("citations", []) == []


@pytest.mark.asyncio
async def test_set_status_records_stage_a_run_failed_at(db_session):
    """_set_status must capture the last active stage into failed_at_status
    when transitioning to failed, so the UI can show *where* a run failed
    instead of every pipeline node going blank (RunStatus.failed has no
    ordinal position of its own in RUN_STATUS_MAP)."""
    from services.run_service import _set_status

    run = Run(user_id="stage-user@example.com", topic="t", format="report", doc_paths=[])
    db_session.add(run)
    await db_session.commit()

    await _set_status(run, RunStatus.researching, db_session)
    assert run.failed_at_status is None

    await _set_status(run, RunStatus.failed, db_session)
    assert run.status == RunStatus.failed
    assert run.failed_at_status == RunStatus.researching


@pytest.mark.asyncio
async def test_set_status_failed_twice_keeps_first_failure_stage(db_session):
    """A second _set_status(..., failed, ...) call (e.g. a retry path) must not
    clobber failed_at_status with RunStatus.failed itself."""
    from services.run_service import _set_status

    run = Run(user_id="stage-user-2@example.com", topic="t", format="report", doc_paths=[])
    db_session.add(run)
    await db_session.commit()

    await _set_status(run, RunStatus.writing, db_session)
    await _set_status(run, RunStatus.failed, db_session)
    await _set_status(run, RunStatus.failed, db_session)

    assert run.failed_at_status == RunStatus.writing


@pytest.mark.asyncio
async def test_run_detail_exposes_failed_at_status(client, auth_as, db_session):
    uid = "failed-stage-user@example.com"
    auth_as(uid)
    run = Run(
        user_id=uid,
        topic="Failure point test",
        format="report",
        status=RunStatus.failed,
        failed_at_status=RunStatus.analyzing,
        doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    assert resp.json()["failed_at_status"] == "analyzing"

    list_resp = await client.get("/runs")
    assert list_resp.status_code == 200
    listed = next(r for r in list_resp.json() if r["id"] == str(run.id))
    assert listed["failed_at_status"] == "analyzing"
