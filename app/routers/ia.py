from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.routers.auth import get_current_user, require_perfil
from app.services.rag_service import consultar, consultar_stream, get_embeddings

router = APIRouter()


class ConsultaRequest(BaseModel):
    pergunta: str


@router.post("/consulta")
async def post_consulta(
    body: ConsultaRequest,
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    """Consulta RAG completa — retorna JSON com a resposta."""
    return await consultar(body.pergunta)


@router.get("/consulta/stream")
async def get_consulta_stream(
    pergunta: str,
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    """Consulta RAG com streaming (SSE) — token a token."""
    return StreamingResponse(
        consultar_stream(pergunta),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embeddings/gerar")
async def post_gerar_embeddings(_: dict = Depends(require_perfil("admin"))):
    """Dispara a task Celery que indexa os contratos ainda sem embedding."""
    from app.tasks.embedding_tasks import task_gerar_embeddings

    task = task_gerar_embeddings.delay()
    return {"task_id": task.id, "status": "enqueued"}


@router.get("/warmup")
async def get_warmup(_: dict = Depends(get_current_user)):
    """Pré-aquece o modelo de embedding (evita ~30s na 1ª consulta)."""
    get_embeddings()
    return {"status": "ok", "modelo": get_embeddings().model_name}
