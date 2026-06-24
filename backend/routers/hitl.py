from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models import Run, RunStatus
from schemas import HitlApproveRequest
from services.run_service import approve_hitl
from auth import get_current_user, assert_run_access

router = APIRouter()


@router.post("/{run_id}/approve")
async def approve(
    run_id: UUID,
    body: HitlApproveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    await assert_run_access(run, user_id, db)
    if run.status not in [
        RunStatus.awaiting_research_approval,
        RunStatus.awaiting_analysis_approval,
        RunStatus.awaiting_final_approval,
    ]:
        raise HTTPException(400, f"Run is not awaiting HITL (status: {run.status})")
    await approve_hitl(str(run_id), body.instruction)
    return {"status": "resumed"}
