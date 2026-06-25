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
    task_soft_time_limit=600,   # SIGTERM after 10 min; task can clean up
    task_time_limit=660,         # SIGKILL after 11 min if still running
    task_routes={
        "execute_run_task": {"queue": "default"},
        "ingest_doc_task":  {"queue": "default"},
    },
)

@celery_app.task(name="execute_run_task")
def execute_run_task(run_id: str):
    import asyncio
    from uuid import UUID
    from services.run_service import execute_run
    asyncio.run(execute_run(UUID(run_id)))


@celery_app.task(name="ingest_doc_task")
def ingest_doc_task(doc_id: str):
    import asyncio
    from uuid import UUID
    from services.ingest_service import ingest_doc
    asyncio.run(ingest_doc(UUID(doc_id)))
