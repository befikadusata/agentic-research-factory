"""
Regression tests for the segmented HITL pipeline.

execute_run now runs ONE segment per invocation and durably pauses at each
human-in-the-loop gate (persisting an `awaiting_*` status and releasing the
worker) instead of blocking a single task through the whole run. The state
machine advances across separate tasks; `run_driver` pumps that in-process.

These verify:
  * each stage is gated behind an approval (no leaking finished downstream work
    onto an earlier approval screen),
  * a review-triggered research retry is re-surfaced for a second approval,
  * token/cost rows are logged exactly once per agent across the segments,
  * autonomous (monitor-spawned) runs complete WITHOUT any operator approval
    and reach finalize_monitored_run (C2).
"""
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select as sa_select
import database
from database import AsyncSessionLocal
from models import Run, RunStatus, RunCost, Monitor
from services.run_service import execute_run
import agents.crew as crew_module


@pytest.fixture(autouse=True)
async def _fresh_engine_pool():
    """execute_run uses the module-level AsyncSessionLocal (not the per-test
    `db_session` fixture's engine), whose pooled asyncpg connections don't
    survive a fresh event loop across test functions (pytest-asyncio uses a new
    loop per test). Disposing the pool forces fresh connections bound to this
    test's loop."""
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


async def _make_run(db, **overrides) -> Run:
    fields = dict(
        id=uuid.uuid4(), user_id="test_user", topic="test topic", format="report",
        vertical=None, doc_paths=[], status=RunStatus.pending,
    )
    fields.update(overrides)
    run = Run(**fields)
    db.add(run)
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_execute_run_gates_stages_and_reshows_retried_research(monkeypatch, redis_pool, run_driver):
    """Combines two scenarios in one test (rather than two functions) because
    module-level AsyncSessionLocal's pooled asyncpg connections don't survive a
    fresh event loop across separate test functions."""

    # ── Scenario 1: PASS on first review — exactly 3 gates, no downstream leak ──
    _install_fake_graph(monkeypatch, review_sequence=["PASS"])

    seen = []

    async def observer(run):
        seen.append({
            "status": run.status,
            "research_output": run.research_output,
            "analysis_output": run.analysis_output,
            "final_output": run.final_output,
        })

    async with AsyncSessionLocal() as db:
        run = await _make_run(db)
        run_id = run.id

    await run_driver(run_id, observer=observer)

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
        # Each agent's usage is logged exactly once, despite the run spanning
        # several segments/tasks.
        assert sorted(c.agent_name for c in costs) == ["analyst", "editor", "researcher", "writer"]

    # ── Scenario 2: FAIL then PASS — retried research must be re-approved ────────
    _install_fake_graph(monkeypatch, review_sequence=["FAIL", "PASS"])

    research_summaries = []

    async def observer_retry(run):
        if run.status == RunStatus.awaiting_research_approval:
            research_summaries.append(run.research_output)

    async with AsyncSessionLocal() as db:
        run = await _make_run(db)
        run_id = run.id

    await run_driver(run_id, observer=observer_retry)

    # A review-triggered research retry must be surfaced for a second approval,
    # not silently redone after the user already approved the first draft.
    assert research_summaries == ["RESEARCH", "RESEARCH-retry"]

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.complete


@pytest.mark.asyncio
async def test_stale_approval_cannot_skip_a_gate(monkeypatch, redis_pool, run_driver):
    """A duplicate/stale resume tagged with a gate the run has already left must
    be a no-op — it must not advance the *next* gate without its own approval."""
    _install_fake_graph(monkeypatch, review_sequence=["PASS"])

    async with AsyncSessionLocal() as db:
        run = await _make_run(db)
        run_id = run.id

    # Advance only through the research gate → run now parks at the analysis gate.
    await run_driver(run_id, approve=False)          # start → awaiting_research_approval
    await execute_run(run_id, RunStatus.awaiting_research_approval.value)  # → awaiting_analysis_approval

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.awaiting_analysis_approval

    # A second (stale) approval of the *research* gate must not run the write
    # segment / skip the analysis approval.
    await execute_run(run_id, RunStatus.awaiting_research_approval.value)

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.awaiting_analysis_approval
        assert not run.final_output


@pytest.mark.asyncio
async def test_autonomous_monitor_run_completes_without_approval(monkeypatch, redis_pool, run_driver):
    """C2: a monitor-spawned run has no human at the gates. It must auto-advance
    through every stage on its own and reach completion + finalize_monitored_run,
    with NO operator approval (approve=False)."""
    _install_fake_graph(monkeypatch, review_sequence=["PASS"])

    async with AsyncSessionLocal() as db:
        monitor = Monitor(
            id=uuid.uuid4(), user_id="test_user", name="watch", topic="test topic",
            format="report", interval_minutes=60,
            next_run_at=datetime.now(timezone.utc),
        )
        db.add(monitor)
        await db.commit()
        monitor_id = monitor.id

        run = await _make_run(db, monitor_id=monitor_id)
        run_id = run.id

    # approve=False: no operator ever approves. Only the autonomous self-advance
    # can carry the run to completion.
    steps = await run_driver(run_id, approve=False)

    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.complete
        assert run.final_output == "DRAFT-EDITED"
        # finalize_monitored_run ran and recorded the baseline diff.
        assert run.metrics.get("monitor_diff", {}).get("baseline") is True

    assert steps > 1  # it genuinely advanced across multiple segments
