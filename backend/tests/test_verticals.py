import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from services.run_service import execute_run
from models import Run
import uuid
import asyncio


@pytest.mark.asyncio
async def test_create_run_unknown_vertical_rejected(client, mock_user):
    """Unknown vertical should return 422 validation error."""
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
    """Valid vertical should pass schema validation."""
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
    """Runs without a vertical should still work (backwards compatible)."""
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
    """B2B sales vertical should be accepted and persisted."""
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
    """Founder strategy vertical should be accepted."""
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
    """Missing required vertical inputs should return 422 validation error."""
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
async def test_execute_run_task_routing():
    """Verify task routing logic assigns correct task_type based on vertical."""
    mock_run_lead = Run(
        id=uuid.uuid4(),
        topic="Stripe",
        vertical="b2b_sales_lead_intel",
        vertical_inputs={"company_url": "stripe.com"},
        format="report"
    )
    
    mock_run_report = Run(
        id=uuid.uuid4(),
        topic="Notion",
        vertical="marketing_competitor_briefs",
        vertical_inputs={"competitor_name": "Notion"},
        format="report"
    )

    with patch("services.run_service.AsyncSessionLocal") as MockSession:
        session_instance = MagicMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=session_instance)
        session_instance.commit = AsyncMock()
        session_instance.refresh = AsyncMock()
        session_instance.get = AsyncMock()
        
        with patch("services.run_service._invoke_supervisor_with_retry") as mock_invoke:
            with patch("services.run_service._wait_for_hitl", new_callable=AsyncMock) as mock_hitl:
                # Test lead_intel routing
                session_instance.get.return_value = mock_run_lead
                mock_invoke.side_effect = lambda s, state, **kwargs: {**state, "research_output": "Lead data", "analysis_output": "Analyzed", "final_output": "Done"}
                mock_hitl.return_value = "continue"
                
                await execute_run(mock_run_lead.id)
                
                # Check the first call (Research stage)
                first_call_state = mock_invoke.call_args_list[0][0][1]
                assert first_call_state["task_type"] == "lead_intel"
                
                # Test research_report routing
                mock_invoke.reset_mock()
                session_instance.get.return_value = mock_run_report
                
                await execute_run(mock_run_report.id)
                first_call_state = mock_invoke.call_args_list[0][0][1]
                assert first_call_state["task_type"] == "research_report"
