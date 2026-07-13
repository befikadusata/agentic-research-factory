"""Shared run-creation + task-dispatch helpers.

Both the /runs API and the monitor dispatcher need to turn a set of run
parameters into a persisted Run plus a queued pipeline task. Keeping that in one
place means the two callers can't drift (e.g. forget to set a new column).

Lives in its own light module rather than run_service.py so importing it (from
the FastAPI router) doesn't pull in the heavy pipeline/LLM stack.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models import Run
from celery_app import execute_run_task


def build_run(
    *,
    user_id: str,
    topic: str,
    format: str,
    doc_paths: Optional[list] = None,
    workspace_id: Optional[UUID] = None,
    vertical: Optional[str] = None,
    vertical_inputs: Optional[dict] = None,
    monitor_id: Optional[UUID] = None,
) -> Run:
    """Construct a Run row (unpersisted). Callers add/commit it themselves so
    they control the surrounding transaction — the dispatcher, for instance,
    commits the run and its monitor's advanced schedule atomically."""
    return Run(
        user_id=user_id,
        topic=topic,
        format=format,
        doc_paths=doc_paths or [],
        workspace_id=workspace_id,
        vertical=vertical,
        vertical_inputs=vertical_inputs or {},
        monitor_id=monitor_id,
    )


async def enqueue_run(db: AsyncSession, **fields) -> Run:
    """Create a Run, commit it, and queue its pipeline task. The common path for
    one-off runs from the API. `fields` are forwarded to `build_run`."""
    run = build_run(**fields)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    execute_run_task.delay(str(run.id))
    return run
