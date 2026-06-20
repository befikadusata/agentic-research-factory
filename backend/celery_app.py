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
    task_routes={"execute_run_task": {"queue": "default"}},
)

@celery_app.task(name="execute_run_task")
def execute_run_task(run_id: str):
    import asyncio
    from uuid import UUID
    from services.run_service import execute_run
    asyncio.run(execute_run(UUID(run_id)))
