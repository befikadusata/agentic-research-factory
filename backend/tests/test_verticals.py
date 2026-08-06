import uuid
from unittest.mock import AsyncMock, patch

import pytest

from models import Run
from services.run_service import execute_run


@pytest.mark.asyncio
async def test_create_run_unknown_vertical_rejected(client, mock_user):
    payload = {
        "topic": "Test vertical validation",
        "format": "report",
        "doc_ids": [],
        "vertical": "nonexistent_vertical",
        "vertical_inputs": {},
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert "nonexistent_vertical" in str(body).lower() or "vertical" in str(body).lower()


@pytest.mark.asyncio
async def test_create_run_valid_vertical_accepted(client, mock_user):
    payload = {
        "topic": "Acme Corp competitive analysis",
        "format": "report",
        "doc_ids": [],
        "vertical": "marketing_competitor_briefs",
        "vertical_inputs": {
            "competitor_name": "Notion",
            "our_product": "AI writing assistant",
        },
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["vertical"] == "marketing_competitor_briefs"


@pytest.mark.asyncio
async def test_create_run_null_vertical_accepted(client, mock_user):
    payload = {
        "topic": "General research topic",
        "format": "report",
        "doc_ids": [],
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data.get("vertical") is None


@pytest.mark.asyncio
async def test_create_run_b2b_sales_vertical(client, mock_user):
    payload = {
        "topic": "https://stripe.com lead intel",
        "format": "report",
        "doc_ids": [],
        "vertical": "b2b_sales_lead_intel",
        "vertical_inputs": {
            "company_url": "https://stripe.com",
            "target_role": "VP Engineering",
        },
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["vertical"] == "b2b_sales_lead_intel"


@pytest.mark.asyncio
async def test_create_run_founder_vertical(client, mock_user):
    payload = {
        "topic": "AI legal tech market analysis",
        "format": "summary",
        "doc_ids": [],
        "vertical": "founder_strategy_briefs",
        "vertical_inputs": {
            "market_segment": "AI-powered legal tech for SMBs",
            "stage": "Seed",
            "key_question": "Is now the right time to enter?",
        },
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["vertical"] == "founder_strategy_briefs"


@pytest.mark.asyncio
async def test_create_run_missing_required_vertical_inputs_rejected(client, mock_user):
    payload = {
        "topic": "Test missing inputs",
        "format": "report",
        "doc_ids": [],
        "vertical": "marketing_competitor_briefs",
        "vertical_inputs": {},  # competitor_name is required
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert "missing required vertical input" in str(body).lower()

@pytest.mark.asyncio
async def test_create_run_invalid_url_field_rejected(client, mock_user):
    """A non-URL value in a `type: url` field should return 422."""
    payload = {
        "topic": "Test invalid url field",
        "format": "report",
        "doc_ids": [],
        "vertical": "b2b_sales_lead_intel",
        "vertical_inputs": {
            "company_url": "not a url",
        },
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert "company_url" in str(body).lower()


@pytest.mark.asyncio
async def test_create_run_invalid_select_field_rejected(client, mock_user):
    """A value outside the declared options for a `type: select` field should return 422."""
    payload = {
        "topic": "Test invalid select field",
        "format": "report",
        "doc_ids": [],
        "vertical": "founder_strategy_briefs",
        "vertical_inputs": {
            "market_segment": "AI legal tech",
            "stage": "Definitely Not A Real Stage",
        },
    }
    response = await client.post("/runs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert "stage" in str(body).lower()


@pytest.mark.asyncio
async def test_execute_run_task_routing(engine, redis_pool):
    """The start segment must derive task_type from the run's vertical: a
    lead_intel vertical yields "lead_intel", a research vertical yields
    "research_report". We capture the state handed to the graph on the first
    invoke and stop the run right there (the gate is stubbed out)."""
    import database
    from database import AsyncSessionLocal
    from models import RunStatus

    await database.engine.dispose()

    async def _make(vertical, vertical_inputs):
        async with AsyncSessionLocal() as db:
            run = Run(
                id=uuid.uuid4(), user_id="test_user", topic="X", format="report",
                vertical=vertical, vertical_inputs=vertical_inputs,
                status=RunStatus.pending, doc_paths=[],
            )
            db.add(run)
            await db.commit()
            return run.id

    lead_id   = await _make("b2b_sales_lead_intel", {"company_url": "stripe.com"})
    report_id = await _make("marketing_competitor_briefs", {"competitor_name": "Notion"})

    with patch("services.run_service._invoke_supervisor_with_retry") as mock_invoke, \
         patch("services.run_service._enter_gate", new_callable=AsyncMock), \
         patch("services.run_service.evaluate_output", new_callable=AsyncMock, return_value={}), \
         patch("services.run_service.emit", new_callable=AsyncMock):

        mock_invoke.side_effect = lambda s, state, config=None, **kwargs: {
            **(state or {}),
            "research_output": "Lead data", "analysis_output": "Analyzed", "final_output": "Done",
        }

        await execute_run(lead_id)
        assert mock_invoke.call_args_list[0][0][1]["task_type"] == "lead_intel"

        mock_invoke.reset_mock()
        await execute_run(report_id)
        assert mock_invoke.call_args_list[0][0][1]["task_type"] == "research_report"
