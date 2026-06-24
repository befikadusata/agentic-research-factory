from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from uuid import UUID
from typing import Optional
from database import get_db
from schemas import CreateRunRequest, RunResponse, RunDetailResponse
from models import Run, WorkspaceMember, RunStatus
from celery_app import execute_run_task # NEW
from auth import get_current_user

router = APIRouter()


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: CreateRunRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = Run(
        user_id=user_id,
        topic=body.topic,
        format=body.format,
        doc_paths=body.doc_ids,  # store UUIDs; run_service resolves file paths via Document table
        workspace_id=body.workspace_id,
        vertical=body.vertical,
        vertical_inputs=body.vertical_inputs,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    execute_run_task.delay(str(run.id))
    return run


@router.get("", response_model=list[RunResponse])
async def list_runs(
    workspace_id: Optional[UUID] = Query(default=None),
    status: Optional[RunStatus] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if workspace_id:
        member = await db.get(WorkspaceMember, (workspace_id, user_id))
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
        q = select(Run).where(Run.workspace_id == workspace_id)
    else:
        q = select(Run).where(Run.user_id == user_id)

    if status is not None:
        q = q.where(Run.status == status)

    result = await db.execute(q.order_by(Run.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    # Allow access if owner OR workspace member
    if run.user_id != user_id:
        if run.workspace_id:
            member = await db.get(WorkspaceMember, (run.workspace_id, user_id))
            if not member:
                raise HTTPException(404, "Run not found")
        else:
            raise HTTPException(404, "Run not found")
    return run
