"""
Benchmark smoke test — runs execute_run against the real LangGraph supervisor,
with fake leaf-node functions swapped in for the CrewAI-backed ones (same
technique as test_run_service_hitl.py's `_install_fake_graph`).

§11.5 regression: this test used to patch `_invoke_supervisor_with_retry` with
a fake that just merged hardcoded strings into state, so the real graph in
crew.py (routing, checkpointer, interrupt_before) never ran — it couldn't have
caught the HITL orchestration bug that the §5.1 fix addressed. It also mocked
`evaluate_output` wholesale and asserted `eval_scores["overall"] >= 70` against
`FAKE_EVAL_SCORES`, a constant defined in this same file, so the "quality bar"
assertion could never fail. Now only the eval LLM call boundary (`acompletion`)
is faked; the real graph routing/interrupt/resume logic and the real
`evaluate_output` JSON-parsing both execute for real, and the run is driven
across its segmented HITL gates via the `run_driver` fixture (operator approving
each stage) rather than a single blocking execute_run call.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select as sa_select

import agents.crew as crew_module
from database import AsyncSessionLocal
from models import Run, RunCost, RunStatus, Workspace
from services.run_service import execute_run

# 4 topics (1 from each category in eval_set.md)
BENCHMARK_SUBSET = [
    {"topic": "Kubernetes cost optimization for SaaS", "format": "lead_intel", "vertical": None},
    {"topic": "https://linear.app", "format": "lead_intel", "vertical": "b2b_sales"},
    {"topic": "Notion competitor analysis", "format": "lead_intel", "vertical": "marketing"},
    {"topic": "AI legal tech SMB market viability", "format": "lead_intel", "vertical": "founder"},
]

FAKE_EVAL_SCORES = {
    "accuracy": 82, "relevance": 85, "completeness": 78,
    "writing_quality": 80, "overall": 81, "issues": [],
}


def _install_fake_graph(monkeypatch):
    """Swap the CrewAI-backed node functions for cheap fakes, then rebuild the
    graph so it picks them up, preserving the real routing/interrupt/checkpointer
    configuration under test."""
    def fake_plan(state):
        return {"plan_output": "PLAN"}

    def fake_research(state):
        return {
            "research_output": "Draft",
            "token_usages": [{"agent_name": "researcher", "prompt_tokens": 500, "completion_tokens": 200}],
        }

    def fake_analyse(state):
        return {"analysis_output": "Analyzed"}

    def fake_review(state):
        return {"review_output": "PASS", "retry_count": state.get("retry_count", 0) + 1}

    def fake_write(state):
        return {"final_output": "Final Output"}

    def fake_edit(state):
        return {"final_output": state["final_output"]}

    monkeypatch.setattr(crew_module, "node_plan", fake_plan)
    monkeypatch.setattr(crew_module, "node_research", fake_research)
    monkeypatch.setattr(crew_module, "node_analyse", fake_analyse)
    monkeypatch.setattr(crew_module, "node_review", fake_review)
    monkeypatch.setattr(crew_module, "node_write", fake_write)
    monkeypatch.setattr(crew_module, "node_edit", fake_edit)

    fresh_graph = crew_module.build_graph()
    monkeypatch.setattr(crew_module, "supervisor", fresh_graph)
    return fresh_graph


def _fake_eval_completion(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_benchmark_smoke(redis_pool, monkeypatch, run_driver):
    # run_driver drives the run via the module-level AsyncSessionLocal, whose
    # pooled asyncpg connections don't survive a fresh event loop across test
    # functions (pytest-asyncio uses a new loop per test). Dispose so the pool
    # rebinds to this test's loop.
    import database
    await database.engine.dispose()

    _install_fake_graph(monkeypatch)

    eval_response = _fake_eval_completion(json.dumps(FAKE_EVAL_SCORES))

    async with AsyncSessionLocal() as db:
        ws = Workspace(name="test_ws", owner_id="test_user")
        db.add(ws)
        await db.commit()
        workspace_id = ws.id

        for item in BENCHMARK_SUBSET:
            run_id = uuid.uuid4()
            new_run = Run(
                id=run_id,
                user_id="test_user",
                topic=item["topic"],
                format=item["format"],
                vertical=item["vertical"],
                workspace_id=workspace_id,
            )
            db.add(new_run)
            await db.commit()

            with patch("services.eval_service.acompletion", AsyncMock(return_value=eval_response)):
                await run_driver(run_id)

            async with AsyncSessionLocal() as db2:
                run = await db2.get(Run, run_id)

                assert run.status == RunStatus.complete
                assert "Final Output" in run.final_output

                # Latency recorded
                assert "latency_sec" in run.metrics
                assert run.metrics["latency_sec"] < 60

                # Eval scores written and meet minimum quality bar
                assert run.metrics.get("eval_scores") is not None
                assert run.metrics["eval_scores"]["overall"] >= 70

                # Citations stored as a list, not an integer
                assert isinstance(run.metrics.get("citations"), list)

                # At least one cost row written per run
                costs_result = await db2.execute(
                    sa_select(RunCost).where(RunCost.run_id == run_id)
                )
                costs = costs_result.scalars().all()
                assert len(costs) >= 1
