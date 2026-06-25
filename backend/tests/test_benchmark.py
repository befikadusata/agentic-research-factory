import pytest
from services.run_service import execute_run
from models import Run, RunCost, Workspace, RunStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from database import AsyncSessionLocal
import uuid
from unittest.mock import patch, AsyncMock

# 4 topics (1 from each category in eval_set.md)
BENCHMARK_SUBSET = [
    {"topic": "Kubernetes cost optimization for SaaS", "format": "lead_intel", "vertical": None},
    {"topic": "https://linear.app", "format": "lead_intel", "vertical": "b2b_sales"},
    {"topic": "Notion competitor analysis", "format": "lead_intel", "vertical": "marketing"},
    {"topic": "AI legal tech SMB market viability", "format": "lead_intel", "vertical": "founder"},
]

FAKE_TOKEN_USAGES = [
    {"agent_name": "research_output", "prompt_tokens": 500, "completion_tokens": 200},
]

FAKE_EVAL_SCORES = {
    "accuracy": 82, "relevance": 85, "completeness": 78,
    "writing_quality": 80, "overall": 81, "issues": [],
}


async def _fake_invoke(sup, state, **kwargs):
    return {
        **state,
        "research_output": "Draft",
        "analysis_output": "Analyzed",
        "final_output": "Final Output",
        "token_usages": FAKE_TOKEN_USAGES,
    }


@pytest.mark.asyncio
async def test_benchmark_smoke(redis_pool):
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

            with patch("services.run_service.evaluate_output", new_callable=AsyncMock) as mock_eval:
                mock_eval.return_value = FAKE_EVAL_SCORES
                with patch(
                    "services.run_service._invoke_supervisor_with_retry",
                    new_callable=AsyncMock,
                ) as mock_invoke:
                    with patch(
                        "services.run_service._wait_for_hitl", new_callable=AsyncMock
                    ) as mock_hitl:
                        mock_invoke.side_effect = _fake_invoke
                        mock_hitl.return_value = "continue"
                        await execute_run(run_id)

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
