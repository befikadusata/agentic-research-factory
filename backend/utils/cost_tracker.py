from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import RunCost
from logger import logger

async def log_cost(db: AsyncSession, run_id: str, agent_name: str, input_tokens: int, output_tokens: int, total_cost: float):
    cost_entry = RunCost(
        run_id=run_id,
        agent_name=agent_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost=total_cost
    )
    db.add(cost_entry)
    await db.commit()


async def run_cost_total(run_id) -> float:
    """Sum of every run_costs row for a run — the run's spend so far. Used to seed
    the graph's in-flight budget check across segments (each segment runs in a
    fresh process, so the running total has to be read back from the DB)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.coalesce(func.sum(RunCost.total_cost), 0.0)).where(RunCost.run_id == run_id)
        )
        return float(result.scalar() or 0.0)


async def log_direct_call(run_id, agent_name: str, response, routing_agent: str | None = None) -> None:
    """Persist the cost of a *direct* litellm call (the eval-confidence judge, the
    monitor diff) that bypasses the crew-node token accounting and so used to be
    invisible in run_costs / the /analytics/costs endpoint.

    `routing_agent` is the role the call was routed as (for served-model
    reconciliation); `agent_name` is the label the cost row is filed under.
    Best-effort — a logging failure must never break the call it measures."""
    try:
        from services.llm_router import reconcile_served_model
        from utils.pricing import calculate_cost

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        model = reconcile_served_model(routing_agent or agent_name, getattr(response, "model", None))
        cost = calculate_cost(model, prompt_tokens, completion_tokens)
        async with AsyncSessionLocal() as db:
            await log_cost(db, run_id, agent_name, prompt_tokens, completion_tokens, cost)
    except Exception as e:
        logger.warning("direct_cost_log_failed", agent_name=agent_name, error=str(e))


# ── side-cost buffer for synchronous in-crew direct calls ─────────────────────
# The RAG query_rewriter fires its own litellm call from *inside* the researcher
# crew node's tool loop (sync, no run_id/event-loop in scope), so it can't log
# cost the async way. Instead it appends here; _run_crew_node drains the buffer
# after kickoff and folds it into the node's token_usages, which run_service then
# persists through the normal cost path. Process-global and reset per node, which
# is sound under the pipeline's Celery --concurrency=1 (one crew node runs at a
# time — the same invariant resolve_actual_model already relies on).
_side_costs: list[dict] = []


def reset_side_costs() -> None:
    _side_costs.clear()


def record_side_cost(agent_name: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    _side_costs.append({
        "agent_name":        agent_name,
        "model":             model,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    })


def take_side_costs() -> list[dict]:
    out = list(_side_costs)
    _side_costs.clear()
    return out
