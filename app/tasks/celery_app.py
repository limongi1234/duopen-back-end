from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "duopen",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.ml_tasks",
        "app.tasks.embedding_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,
)
