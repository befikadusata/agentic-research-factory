from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional
from database import get_db
from schemas import CreateRunRequest, RunResponse, RunDetailResponse
from models import Run, WorkspaceMember, RunStatus, Document
from services.run_dispatch import enqueue_run
from auth import get_current_user

router = APIRouter()


def normalize_run_logs(entries: object) -> list[dict[str, str]]:
    """Convert persisted event envelopes (including historical bad data) into UI logs."""
    if not isinstance(entries, list):
        return []

    normalized: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        event_type = str(entry.get("type") or "log")
        payload = entry.get("data") if isinstance(entry.get("data"), dict) else entry
        agent = payload.get("agent")
        message = payload.get("message")

        if message is None and event_type == "status" and payload.get("status") is not None:
            message = f"Status changed to {payload['status']}"
        elif message is None and event_type == "hitl_required" and payload.get("stage") is not None:
            message = f"Human approval required at {payload['stage']}"
        elif message is None and event_type == "complete":
            message = "Run completed"

        if message is None:
            continue
        if not isinstance(message, str):
            try:
                import json
                message = json.dumps(message, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                message = str(message)

        message = message.strip()
        if not message:
            continue
        normalized.append({
            "agent": str(agent or ("error" if event_type == "error" else "system")),
            "message": message,
            "ts": str(entry.get("ts") or payload.get("ts") or ""),
        })
    return normalized


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: CreateRunRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if body.workspace_id:
        member = await db.get(WorkspaceMember, (body.workspace_id, user_id))
        if not member:
            raise HTTPException(403, "Not a member of this workspace")

    if body.doc_ids:
        try:
            doc_uuids = [UUID(d) for d in body.doc_ids]
        except ValueError:
            raise HTTPException(400, "Invalid doc_id")
        result = await db.execute(select(Document).where(Document.id.in_(doc_uuids)))
        docs = result.scalars().all()
        if len(docs) != len(doc_uuids) or any(d.workspace_id != body.workspace_id for d in docs):
            raise HTTPException(403, "One or more documents are not accessible in this workspace")

    run = await enqueue_run(
        db,
        user_id=user_id,
        topic=body.topic,
        format=body.format,
        doc_paths=body.doc_ids,  # store UUIDs; run_service resolves file paths via Document table
        workspace_id=body.workspace_id,
        vertical=body.vertical,
        vertical_inputs=body.vertical_inputs,
    )
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
    result = await db.execute(
        select(Run).where(Run.id == run_id).options(selectinload(Run.costs))
    )
    run = result.scalar_one_or_none()
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
    return RunDetailResponse(
        **{k: v for k, v in run.__dict__.items() if not k.startswith("_") and k != "logs"},
        logs=normalize_run_logs(run.logs),
        citations=(run.metrics or {}).get("citations", []),
    )
