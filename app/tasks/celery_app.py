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
    # Mantém o estado das tasks por 1h para monitoramento via /ml/status
    result_expires=3600,
    # Celery 5+: tenta reconectar ao broker no startup (ex.: Redis do Railway)
    broker_connection_retry_on_startup=True,
)

# ── Retry com backoff exponencial ─────────────────────────────────────────────
RETRY_BACKOFF_BASE = 2  # segundos
RETRY_BACKOFF_MAX = 600  # teto de 10 min entre tentativas


def backoff_countdown(retries: int) -> int:
    """Atraso (em segundos) entre tentativas: 2, 4, 8, 16, ... limitado a RETRY_BACKOFF_MAX."""
    return min(RETRY_BACKOFF_BASE * (2 ** retries), RETRY_BACKOFF_MAX)
