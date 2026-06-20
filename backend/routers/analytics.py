from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import Run, RunStatus
from auth import get_current_user

router = APIRouter()

@router.get("/metrics")
async def get_global_metrics(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Aggregate metrics across completed runs."""
    result = await db.execute(
        select(Run.metrics).where(Run.status == RunStatus.complete)
    )
    all_metrics = [r[0] for r in result.all()]
    
    if not all_metrics:
        return {"count": 0, "averages": {}}

    count = len(all_metrics)
    total_latency = sum(m.get("latency_sec", 0) for m in all_metrics)
    total_citations = sum(m.get("citations", 0) for m in all_metrics)
    
    # Eval scores averages
    scores = [m.get("eval", {}) for m in all_metrics if m.get("eval")]
    avg_accuracy = sum(s.get("accuracy", 0) for s in scores) / len(scores) if scores else 0
    avg_relevance = sum(s.get("relevance", 0) for s in scores) / len(scores) if scores else 0
    
    return {
        "count": count,
        "averages": {
            "latency_sec": total_latency / count,
            "citations": total_citations / count,
            "accuracy": avg_accuracy,
            "relevance": avg_relevance,
        }
    }
