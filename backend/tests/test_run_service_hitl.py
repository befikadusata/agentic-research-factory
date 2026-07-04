"""
Regression tests for run_service.execute_run actually gating each stage behind
a human approval, instead of the pre-fix behavior where the graph ran research
-> analyse -> review -> write -> edit -> END in one shot and the "approve
research" screen just showed already-finished work.
"""
import uuid
import pytest
from sqlalchemy import select as sa_select
import database
from database import AsyncSessionLocal
from models import Run, RunStatus, RunCost
from services.run_service import execute_run
import agents.crew as crew_module


@pytest.fixture(autouse=True)
async def _fresh_engine_pool():
    """execute_run uses the module-level AsyncSessionLocal (not the per-test
    `db_session` fixture's engine), whose pooled asyncpg connections don't
    survive a fresh event loop across test functions (pytest-asyncio uses a new
    loop per test) — the same class of bug as the pre-existing
    get_redis_client() event-loop leak (utils/redis_client.py). Disposing the
    pool here forces fresh connections bound to this test's loop."""
    await database.engine.dispose()
    yield


def _install_fake_graph(monkeypatch, review_sequence):
    reviews = iter(review_sequence)

    def fake_plan(state):
        return {"plan_output": "PLAN"}

    def fake_research(state):
        tag = "-retry" if "FAIL" in (state.get("review_output") or "") else ""
        return {
            "research_output": f"RESEARCH{tag}",
            "token_usages": [{"agent_name": "researcher", "prompt_tokens": 10, "completion_tokens": 5}],
        }

    def fake_analyse(state):
        return {
            "analysis_output": "ANALYSIS",
            "token_usages": [{"agent_name": "analyst", "prompt_tokens": 20, "completion_tokens": 8}],
        }

    def fake_review(state):
        return {"review_output": next(reviews), "retry_count": state.get("retry_count", 0) + 1}

    def fake_write(state):
        return {
            "final_output": "DRAFT",
            "token_usages": [{"agent_name": "writer", "prompt_tokens": 30, "completion_tokens": 12}],
        }

    def fake_edit(state):
        return {
            "final_output": state["final_output"] + "-EDITED",
            "token_usages": [{"agent_name": "editor", "prompt_tokens": 15, "completion_tokens": 6}],
        }

    monkeypatch.setattr(crew_module, "node_plan", fake_plan)
    monkeypatch.setattr(crew_module, "node_research", fake_research)
    monkeypatch.setattr(crew_module, "node_analyse", fake_analyse)
    monkeypatch.setattr(crew_module, "node_review", fake_review)
    monkeypatch.setattr(crew_module, "node_write", fake_write)
    monkeypatch.setattr(crew_module, "node_edit", fake_edit)

    fresh_graph = crew_module.build_graph()
    monkeypatch.setattr(crew_module, "supervisor", fresh_graph)
    return fresh_graph


async def _make_run(db) -> Run:
    run = Run(
        id=uuid.uuid4(), user_id="test_user", topic="test topic", format="report",
        vertical=None, doc_paths=[],
    )
    db.add(run)
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_execute_run_gates_stages_and_reshows_retried_research(monkeypatch, redis_pool):
    """Combines two scenarios in one test (rather than two test functions) because
    module-level AsyncSessionLocal's pooled asyncpg connections don't survive a
    fresh event loop across separate test functions (pytest-asyncio uses a new
    loop per test) — see the pre-existing get_redis_client() event-loop leak this
    codebase already has for the same reason (utils/redis_client.py)."""

    # ── Scenario 1: PASS on first review — exactly 3 gates, no re-run leakage ──
    _install_fake_graph(monkeypatch, review_sequence=["PASS"])

    seen = []

    async def fake_wait_for_hitl(run_id, status, emit_event, summary):
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            seen.append({
                "status": status,
                "research_output": run.research_output,
                "analysis_output": run.analysis_output,
                "final_output": run.final_output,
            })
        return ""

    monkeypatch.setattr("services.run_service._wait_for_hitl", fake_wait_for_hitl)

    async with AsyncSessionLocal() as db:
        run = await _make_run(db)
        run_id = run.id

    await execute_run(run_id)

    assert [s["status"] for s in seen] == [
        RunStatus.awaiting_research_approval,
        RunStatus.awaiting_analysis_approval,
        RunStatus.awaiting_final_approval,
    ]
    # The research-approval gate must fire before analysis has run.
    assert seen[0]["research_output"] == "RESEARCH"
    assert not seen[0]["analysis_output"]
    # The analysis-approval gate must fire before writing has run.
    assert seen[1]["analysis_output"] == "ANALYSIS"
    assert not seen[1]["final_output"]

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.complete
        assert run.final_output == "DRAFT-EDITED"

        costs = (
            await db.execute(sa_select(RunCost).where(RunCost.run_id == run_id))
        ).scalars().all()
        # Each agent's usage is logged exactly once, despite token_usages accumulating
        # across resumes in the checkpointed graph state.
        assert sorted(c.agent_name for c in costs) == ["analyst", "editor", "researcher", "writer"]

    # ── Scenario 2: FAIL then PASS — retried research must be re-approved ──────
    _install_fake_graph(monkeypatch, review_sequence=["FAIL", "PASS"])

    research_summaries = []

    async def fake_wait_for_hitl_retry(run_id, status, emit_event, summary):
        if status == RunStatus.awaiting_research_approval:
            research_summaries.append(summary)
        return ""

    monkeypatch.setattr("services.run_service._wait_for_hitl", fake_wait_for_hitl_retry)

    async with AsyncSessionLocal() as db:
        run = await _make_run(db)
        run_id = run.id

    await execute_run(run_id)

    # A review-triggered research retry must be surfaced for a second approval,
    # not silently redone after the user already approved the first draft.
    assert research_summaries == ["RESEARCH", "RESEARCH-retry"]

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.complete
