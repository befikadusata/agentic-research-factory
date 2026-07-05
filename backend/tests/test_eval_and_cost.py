import json
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from models import Run, RunCost, RunStatus


# ── eval_service ─────────────────────────────────────────────────────────────

def _make_completion_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


VALID_SCORES = {
    "accuracy": 85,
    "relevance": 90,
    "completeness": 78,
    "writing_quality": 88,
    "overall": 85,
    "issues": [],
}


@pytest.mark.asyncio
async def test_evaluate_output_success():
    from services.eval_service import evaluate_output

    raw = json.dumps(VALID_SCORES)
    with patch("services.eval_service.acompletion", AsyncMock(return_value=_make_completion_response(raw))):
        result = await evaluate_output("content", "research", "topic")

    assert result["accuracy"] == 85
    assert result["overall"] == 85
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_evaluate_output_strips_markdown_fence():
    from services.eval_service import evaluate_output

    fenced = f"```json\n{json.dumps(VALID_SCORES)}\n```"
    with patch("services.eval_service.acompletion", AsyncMock(return_value=_make_completion_response(fenced))):
        result = await evaluate_output("content", "research", "topic")

    assert result["accuracy"] == 85


@pytest.mark.asyncio
async def test_evaluate_output_raises_on_malformed_json():
    from services.eval_service import evaluate_output

    with patch("services.eval_service.acompletion", AsyncMock(return_value=_make_completion_response("not json"))):
        with pytest.raises(json.JSONDecodeError):
            await evaluate_output("content", "research", "topic")


@pytest.mark.asyncio
async def test_evaluate_output_propagates_llm_exception():
    from services.eval_service import evaluate_output

    with patch("services.eval_service.acompletion", AsyncMock(side_effect=RuntimeError("API down"))):
        with pytest.raises(RuntimeError, match="API down"):
            await evaluate_output("content", "research", "topic")


# ── cost_tracker ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_cost_writes_run_cost_row(db_session):
    from utils.cost_tracker import log_cost

    run = Run(
        id=uuid.uuid4(), user_id="u1", topic="t", format="report",
        status=RunStatus.pending, doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()

    await log_cost(db_session, run.id, "researcher", input_tokens=500, output_tokens=200, total_cost=0.05)

    result = await db_session.execute(select(RunCost).where(RunCost.run_id == run.id))
    cost = result.scalar_one()
    assert cost.agent_name == "researcher"
    assert cost.input_tokens == 500
    assert cost.output_tokens == 200
    assert abs(cost.total_cost - 0.05) < 0.001


@pytest.mark.asyncio
async def test_log_cost_multiple_agents(db_session):
    from utils.cost_tracker import log_cost

    run = Run(
        id=uuid.uuid4(), user_id="u2", topic="t", format="report",
        status=RunStatus.pending, doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()

    await log_cost(db_session, run.id, "researcher", 100, 50, 0.01)
    await log_cost(db_session, run.id, "writer", 200, 100, 0.02)

    result = await db_session.execute(select(RunCost).where(RunCost.run_id == run.id))
    costs = result.scalars().all()
    assert len(costs) == 2
    names = {c.agent_name for c in costs}
    assert names == {"researcher", "writer"}


@pytest.mark.asyncio
async def test_log_token_usages_computes_real_cost_not_zero(db_session, monkeypatch):
    """§4.1 regression: unlike the tests above (which call log_cost() directly
    with a hand-picked total_cost), this goes through the actual production
    caller — run_service._log_token_usages — which used to hardcode
    total_cost=0.0 regardless of the model or token counts."""
    import services.run_service as run_service_module
    from services.run_service import _log_token_usages

    monkeypatch.setattr(run_service_module, "AsyncSessionLocal", lambda: db_session_cm(db_session))

    run = Run(
        id=uuid.uuid4(), user_id="u3", topic="t", format="report",
        status=RunStatus.pending, doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()

    await _log_token_usages(str(run.id), [
        {"agent_name": "researcher", "model": "gpt-4o", "prompt_tokens": 1000, "completion_tokens": 1000},
    ])

    result = await db_session.execute(select(RunCost).where(RunCost.run_id == run.id))
    cost = result.scalar_one()
    assert cost.total_cost > 0.0
    assert abs(cost.total_cost - 0.0125) < 0.0001


class db_session_cm:
    """Minimal async-context-manager wrapper so a fixture-provided db_session
    can stand in for AsyncSessionLocal()'s real context-manager interface."""
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False
