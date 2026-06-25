import pytest
import uuid
from models import Run, RunCost, RunStatus


async def _make_complete_run(db, user_id: str, metrics: dict) -> Run:
    run = Run(
        id=uuid.uuid4(),
        user_id=user_id,
        topic="test",
        format="report",
        status=RunStatus.complete,
        metrics=metrics,
        doc_paths=[],
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@pytest.mark.asyncio
async def test_metrics_requires_auth(client):
    r = await client.get("/analytics/metrics")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_costs_requires_auth(client):
    r = await client.get("/analytics/costs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_metrics_empty_state(client, mock_user):
    r = await client.get("/analytics/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["averages"] == {}


@pytest.mark.asyncio
async def test_costs_empty_state(client, mock_user):
    r = await client.get("/analytics/costs")
    assert r.status_code == 200
    data = r.json()
    assert data["total_cost_usd"] == 0.0
    assert data["total_input_tokens"] == 0
    assert data["total_output_tokens"] == 0
    assert data["per_agent"] == []


@pytest.mark.asyncio
async def test_metrics_aggregates_completed_runs(client, mock_user, db_session):
    scores1 = {"accuracy": 80, "relevance": 90, "completeness": 70, "writing_quality": 85, "overall": 81}
    scores2 = {"accuracy": 60, "relevance": 70, "completeness": 80, "writing_quality": 75, "overall": 71}

    await _make_complete_run(db_session, mock_user, {
        "latency_sec": 10.0,
        "citations": ["a", "b"],
        "eval_scores": scores1,
    })
    await _make_complete_run(db_session, mock_user, {
        "latency_sec": 20.0,
        "citations": ["c"],
        "eval_scores": scores2,
    })
    # Failed run must NOT be included in averages
    db_session.add(Run(
        id=uuid.uuid4(), user_id=mock_user, topic="t", format="report",
        status=RunStatus.failed, metrics={"latency_sec": 5.0}, doc_paths=[],
    ))
    await db_session.commit()

    r = await client.get("/analytics/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert data["averages"]["latency_sec"] == 15.0
    assert data["averages"]["citations"] == 1.5
    assert abs(data["averages"]["accuracy"] - 70.0) < 0.01
    assert abs(data["averages"]["overall"] - 76.0) < 0.01


@pytest.mark.asyncio
async def test_costs_aggregates_run_costs(client, mock_user, db_session):
    run = await _make_complete_run(db_session, mock_user, {})
    db_session.add_all([
        RunCost(run_id=run.id, agent_name="researcher", input_tokens=100, output_tokens=50, total_cost=0.01),
        RunCost(run_id=run.id, agent_name="writer", input_tokens=200, output_tokens=80, total_cost=0.02),
    ])
    await db_session.commit()

    r = await client.get("/analytics/costs")
    assert r.status_code == 200
    data = r.json()
    assert abs(data["total_cost_usd"] - 0.03) < 0.001
    assert data["total_input_tokens"] == 300
    assert data["total_output_tokens"] == 130
    agent_names = {a["agent_name"] for a in data["per_agent"]}
    assert agent_names == {"researcher", "writer"}
