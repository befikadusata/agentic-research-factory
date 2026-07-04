from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import Run, RunCost, RunStatus, WorkspaceMember
from auth import get_current_user

router = APIRouter()


async def _scope_to_caller(db: AsyncSession, user_id: str, workspace_id: Optional[UUID]):
    """Restrict analytics to the caller's own runs, or a workspace they belong to."""
    if workspace_id:
        member = await db.get(WorkspaceMember, (workspace_id, user_id))
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
        return Run.workspace_id == workspace_id
    return Run.user_id == user_id


@router.get("/metrics")
async def get_global_metrics(
    workspace_id: Optional[UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Aggregate metrics across the caller's completed runs (optionally scoped to a workspace)."""
    scope = await _scope_to_caller(db, user_id, workspace_id)
    result = await db.execute(
        select(Run.metrics).where(Run.status == RunStatus.complete, scope)
    )
    all_metrics = [r[0] for r in result.all() if r[0]]

    if not all_metrics:
        return {"count": 0, "averages": {}}

    count = len(all_metrics)
    total_latency = sum(m.get("latency_sec", 0) for m in all_metrics)
    total_citations = sum(len(m.get("citations") or []) for m in all_metrics)

    scores = [m.get("eval_scores", {}) for m in all_metrics if m.get("eval_scores")]
    n = len(scores)

    def _avg(key):
        return sum(s.get(key, 0) for s in scores) / n if n else 0

    return {
        "count": count,
        "averages": {
            "latency_sec":     total_latency / count,
            "citations":       total_citations / count,
            "accuracy":        _avg("accuracy"),
            "relevance":       _avg("relevance"),
            "completeness":    _avg("completeness"),
            "writing_quality": _avg("writing_quality"),
            "overall":         _avg("overall"),
        },
    }


@router.get("/costs")
async def get_cost_summary(
    workspace_id: Optional[UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Total token usage and cost breakdown by agent, scoped to the caller's own runs (or a workspace they belong to)."""
    scope = await _scope_to_caller(db, user_id, workspace_id)

    total_result = await db.execute(
        select(
            func.sum(RunCost.total_cost).label("total_cost"),
            func.sum(RunCost.input_tokens).label("total_input_tokens"),
            func.sum(RunCost.output_tokens).label("total_output_tokens"),
        ).join(Run, Run.id == RunCost.run_id).where(scope)
    )
    t = total_result.one()

    per_agent_result = await db.execute(
        select(
            RunCost.agent_name,
            func.sum(RunCost.total_cost).label("cost"),
            func.sum(RunCost.input_tokens).label("input_tokens"),
            func.sum(RunCost.output_tokens).label("output_tokens"),
        ).join(Run, Run.id == RunCost.run_id).where(scope).group_by(RunCost.agent_name)
    )

    return {
        "total_cost_usd":       t.total_cost or 0.0,
        "total_input_tokens":   t.total_input_tokens or 0,
        "total_output_tokens":  t.total_output_tokens or 0,
        "per_agent": [
            {
                "agent_name":    r.agent_name,
                "cost":          r.cost or 0.0,
                "input_tokens":  r.input_tokens or 0,
                "output_tokens": r.output_tokens or 0,
            }
            for r in per_agent_result.all()
        ],
    }
