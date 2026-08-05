from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Document, Monitor, Run, WorkspaceMember
from schemas import (
    CreateMonitorRequest,
    MonitorResponse,
    RunResponse,
    UpdateMonitorRequest,
)
from services.run_dispatch import enqueue_run

router = APIRouter()


async def _accessible_monitor(db: AsyncSession, monitor_id: UUID, user_id: str) -> Monitor:
    """Return the monitor if the caller owns it or shares its workspace; else
    404 (never reveal existence to non-members). Mirrors runs' access rule."""
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(404, "Monitor not found")
    if monitor.user_id != user_id:
        if monitor.workspace_id:
            member = await db.get(WorkspaceMember, (monitor.workspace_id, user_id))
            if not member:
                raise HTTPException(404, "Monitor not found")
        else:
            raise HTTPException(404, "Monitor not found")
    return monitor


async def _validate_docs(db: AsyncSession, doc_ids: list[str], workspace_id: UUID | None):
    """Same guard create_run applies: every doc must exist and belong to the
    monitor's workspace."""
    if not doc_ids:
        return
    try:
        doc_uuids = [UUID(d) for d in doc_ids]
    except ValueError:
        raise HTTPException(400, "Invalid doc_id") from None
    result = await db.execute(select(Document).where(Document.id.in_(doc_uuids)))
    docs = result.scalars().all()
    if len(docs) != len(doc_uuids) or any(d.workspace_id != workspace_id for d in docs):
        raise HTTPException(403, "One or more documents are not accessible in this workspace")


@router.post("", response_model=MonitorResponse, status_code=201)
async def create_monitor(
    body: CreateMonitorRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if body.workspace_id:
        member = await db.get(WorkspaceMember, (body.workspace_id, user_id))
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
    await _validate_docs(db, body.doc_ids, body.workspace_id)

    # next_run_at = now so an enabled monitor establishes a baseline run on the
    # next dispatcher tick (the first run is what later runs diff against).
    monitor = Monitor(
        user_id=user_id,
        workspace_id=body.workspace_id,
        name=body.name,
        topic=body.topic,
        format=body.format,
        vertical=body.vertical,
        vertical_inputs=body.vertical_inputs,
        doc_paths=body.doc_ids,
        interval_minutes=body.interval_minutes,
        enabled=body.enabled,
        notify_channel=body.notify_channel,
        next_run_at=datetime.now(UTC),
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return monitor


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    workspace_id: UUID | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if workspace_id:
        member = await db.get(WorkspaceMember, (workspace_id, user_id))
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
        q = select(Monitor).where(Monitor.workspace_id == workspace_id)
    else:
        q = select(Monitor).where(Monitor.user_id == user_id)

    if enabled is not None:
        q = q.where(Monitor.enabled.is_(enabled))

    result = await db.execute(q.order_by(Monitor.created_at.desc()))
    return result.scalars().all()


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await _accessible_monitor(db, monitor_id, user_id)


@router.get("/{monitor_id}/runs", response_model=list[RunResponse])
async def list_monitor_runs(
    monitor_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """The monitor's run history — the timeline the UI renders."""
    await _accessible_monitor(db, monitor_id, user_id)
    result = await db.execute(
        select(Run)
        .where(Run.monitor_id == monitor_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.patch("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: UUID,
    body: UpdateMonitorRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    monitor = await _accessible_monitor(db, monitor_id, user_id)

    if body.name is not None:
        monitor.name = body.name
    if body.interval_minutes is not None:
        monitor.interval_minutes = body.interval_minutes
    if body.notify_channel is not None:
        monitor.notify_channel = body.notify_channel
    if body.enabled is not None:
        # Re-enabling: fire on the next tick rather than honouring a stale
        # next_run_at that may be far in the past or future.
        if body.enabled and not monitor.enabled:
            monitor.next_run_at = datetime.now(UTC)
        monitor.enabled = body.enabled

    await db.commit()
    await db.refresh(monitor)
    return monitor


@router.post("/{monitor_id}/run", response_model=RunResponse, status_code=201)
async def run_monitor_now(
    monitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Spawn a run immediately, out of band from the schedule. Leaves
    next_run_at untouched so the regular cadence continues."""
    monitor = await _accessible_monitor(db, monitor_id, user_id)
    run = await enqueue_run(
        db,
        user_id=monitor.user_id,
        topic=monitor.topic,
        format=monitor.format,
        doc_paths=monitor.doc_paths,
        workspace_id=monitor.workspace_id,
        vertical=monitor.vertical,
        vertical_inputs=monitor.vertical_inputs,
        monitor_id=monitor.id,
    )
    monitor.last_run_id = run.id
    monitor.last_run_at = datetime.now(UTC)
    await db.commit()
    return run


@router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    monitor = await _accessible_monitor(db, monitor_id, user_id)
    # The runs this monitor spawned reference it via runs.monitor_id, which would
    # block the delete. Detach them (SET NULL) rather than destroy research
    # history — they remain as ordinary standalone runs.
    await db.execute(
        update(Run).where(Run.monitor_id == monitor_id).values(monitor_id=None)
    )
    await db.delete(monitor)
    await db.commit()
