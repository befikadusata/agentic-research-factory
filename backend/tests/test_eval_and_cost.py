import json
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from models import Run, RunCost, RunStatus


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


@pytest.mark.asyncio
async def test_evaluate_output_logs_cost_when_run_id_given():
    """The gate eval judge is a direct litellm call, so given a run_id it has to
    persist its own cost under the given agent label or it is counted nowhere."""
    from services.eval_service import evaluate_output

    raw = json.dumps(VALID_SCORES)
    logged = AsyncMock()
    with patch("services.eval_service.acompletion", AsyncMock(return_value=_make_completion_response(raw))), \
         patch("services.eval_service.log_direct_call", logged):
        await evaluate_output("c", "r", "t", run_id="run-1", agent_name="eval_research")

    logged.assert_awaited_once()
    args, kwargs = logged.call_args
    assert args[0] == "run-1"
    assert args[1] == "eval_research"
    assert kwargs.get("routing_agent") == "eval"


@pytest.mark.asyncio
async def test_evaluate_output_skips_cost_log_without_run_id():
    from services.eval_service import evaluate_output

    raw = json.dumps(VALID_SCORES)
    logged = AsyncMock()
    with patch("services.eval_service.acompletion", AsyncMock(return_value=_make_completion_response(raw))), \
         patch("services.eval_service.log_direct_call", logged):
        await evaluate_output("c", "r", "t")

    logged.assert_not_awaited()


@pytest.mark.asyncio
async def test_lead_intel_evaluation_adds_buyer_freshness_and_readiness_dimensions():
    from services.eval_service import evaluate_output

    completion = AsyncMock(return_value=_make_completion_response(json.dumps(VALID_SCORES)))
    with patch("services.eval_service.acompletion", completion):
        await evaluate_output(
            "report", "source ledger", "complete execution brief",
            evaluation_requirements="Buyer-role coverage; title freshness; purchase readiness",
        )

    prompt = completion.await_args.kwargs["messages"][0]["content"]
    assert "Buyer-role coverage" in prompt
    assert "title freshness" in prompt
    assert "purchase readiness" in prompt
    assert '"buyer_role_coverage"' in prompt
    assert '"title_freshness"' in prompt
    assert '"purchase_readiness"' in prompt


def test_query_rewriter_records_side_cost():
    """generate_sub_queries fires its own litellm call inside the researcher's
    tool loop; it must buffer that cost so the crew node can persist it."""
    from services import query_rewriter
    from utils.cost_tracker import reset_side_costs, take_side_costs

    reset_side_costs()
    resp = _make_completion_response('["a", "b"]')
    resp.usage = MagicMock(prompt_tokens=12, completion_tokens=7)
    resp.model = "llama-3.1-8b-instant"

    with patch("services.query_rewriter.completion", MagicMock(return_value=resp)), \
         patch("services.query_rewriter.reconcile_served_model", return_value="groq/llama-3.1-8b-instant"):
        out = query_rewriter.generate_sub_queries("q")

    assert out == ["a", "b"]
    side = take_side_costs()
    assert len(side) == 1
    assert side[0]["agent_name"] == "query_rewriter"
    assert side[0]["model"] == "groq/llama-3.1-8b-instant"
    assert side[0]["prompt_tokens"] == 12
    assert side[0]["completion_tokens"] == 7


@pytest.mark.asyncio
async def test_run_cost_total_sums_rows(db_session, monkeypatch):
    import utils.cost_tracker as ct

    monkeypatch.setattr(ct, "AsyncSessionLocal", lambda: db_session_cm(db_session))
    run = Run(
        id=uuid.uuid4(), user_id="u4", topic="t", format="report",
        status=RunStatus.pending, doc_paths=[],
    )
    db_session.add(run)
    await db_session.commit()

    await ct.log_cost(db_session, run.id, "researcher", 100, 50, 0.01)
    await ct.log_cost(db_session, run.id, "analyst", 200, 100, 0.02)

    total = await ct.run_cost_total(run.id)
    assert abs(total - 0.03) < 1e-9


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
    """Unlike the tests above (which call log_cost() directly with a hand-picked
    total_cost), this goes through the actual production caller,
    run_service._log_token_usages, so it catches a total_cost that ignores the
    model and token counts."""
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
