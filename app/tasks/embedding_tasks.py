from app.tasks.celery_app import celery_app
import logging

log = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def generate_embeddings(self, documento_id: str, texto: str) -> dict:
    try:
        log.info(f"Gerando embeddings para documento {documento_id}")
        # TODO: integrar com OpenAI embeddings via LangChain
        return {"documento_id": documento_id, "status": "completed"}
    except Exception as exc:
        log.error(f"Erro ao gerar embeddings: {exc}")
        raise self.retry(exc=exc)
