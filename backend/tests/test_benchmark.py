import pytest
from services.run_service import execute_run
from models import Run, Workspace, RunStatus
from sqlalchemy.ext.asyncio import AsyncSession
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

@pytest.mark.asyncio
async def test_benchmark_smoke(redis_pool):
    async with AsyncSessionLocal() as db:
        # Create a workspace
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
                workspace_id=workspace_id
            )
            db.add(new_run)
            await db.commit()
    
            # Mock LLM calls and HITL stages to avoid real execution and hanging
            with patch("services.run_service._invoke_supervisor_with_retry") as mock_invoke:
                with patch("services.run_service._wait_for_hitl", new_callable=AsyncMock) as mock_hitl:
                    mock_invoke.side_effect = lambda s, state, **kwargs: {**state, "research_output": "Draft", "analysis_output": "Analyzed", "final_output": "Final Output"}
                    mock_hitl.return_value = "continue"
                    # Execute
                    await execute_run(run_id) 

            # Fetch and assert
            async with AsyncSessionLocal() as db2:
                run = await db2.get(Run, run_id)
                assert run.status == RunStatus.complete
                assert "Final Output" in run.final_output
