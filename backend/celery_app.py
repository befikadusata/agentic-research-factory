from celery import Celery
from config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Each task now runs ONE pipeline segment (research / analyse / write /
    # finalize) and returns — human-in-the-loop waits happen *between* tasks, not
    # inside them (a paused run holds no worker; run_service persists an
    # awaiting_* status and the next segment is queued on approval). So this limit
    # bounds pure compute for a single segment, not a whole multi-gate run, and no
    # longer has to exceed any HITL timeout.
    task_soft_time_limit=600,   # SIGTERM after 10 min; task can clean up
    task_time_limit=660,         # SIGKILL after 11 min if still running
    # Each task runs its own event loop via asyncio.run(). The module-level
    # async SQLAlchemy engine (database.py) binds its asyncpg pool to the first
    # task's loop, so a second task reusing the same worker child fails with
    # "got Future attached to a different loop". Recycle the child after every
    # task so each run gets a fresh process → fresh loop → fresh engine. The
    # fork cost is negligible next to a multi-minute research run.
    worker_max_tasks_per_child=1,
    task_routes={
        "execute_run_task": {"queue": "default"},
        "ingest_doc_task":  {"queue": "default"},
        "dispatch_due_monitors_task": {"queue": "default"},
    },
    # Celery-beat tick that drives continuous monitoring. It only *finds due
    # monitors and enqueues their runs* — the heavy pipeline still runs in a
    # separate execute_run_task child — so a 60s cadence is cheap. Each monitor
    # fires at its own interval_minutes; this just checks who's due.
    beat_schedule={
        "dispatch-due-monitors": {
            "task": "dispatch_due_monitors_task",
            "schedule": 60.0,
        },
    },
)

@celery_app.task(name="execute_run_task")
def execute_run_task(run_id: str, approved_gate: str | None = None):
    # Runs one pipeline segment. approved_gate is None for the initial start, or
    # the awaiting_* status just approved — run_service uses it to advance exactly
    # that gate and to no-op stale/duplicate resumes.
    import asyncio
    from uuid import UUID
    from services.run_service import execute_run
    asyncio.run(execute_run(UUID(run_id), approved_gate))


@celery_app.task(name="ingest_doc_task")
def ingest_doc_task(doc_id: str):
    import asyncio
    from uuid import UUID
    from services.ingest_service import ingest_doc
    asyncio.run(ingest_doc(UUID(doc_id)))


@celery_app.task(name="dispatch_due_monitors_task")
def dispatch_due_monitors_task():
    import asyncio
    from services.monitor_service import dispatch_due_monitors
    asyncio.run(dispatch_due_monitors())
