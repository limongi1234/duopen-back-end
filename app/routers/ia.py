from fastapi import APIRouter, Depends
from app.routers.auth import get_current_user
from app.schemas.ml import RAGQuery, RAGResponse, EmbeddingRequest
from app.services.rag_service import RAGService
from app.tasks.embedding_tasks import generate_embeddings

router = APIRouter()


@router.post("/query", response_model=RAGResponse)
async def consultar_ia(
    body: RAGQuery,
    _: dict = Depends(get_current_user),
):
    service = RAGService()
    return await service.query(body.pergunta, obra_id=body.obra_id, top_k=body.top_k)


@router.post("/embeddings")
async def gerar_embeddings(
    body: EmbeddingRequest,
    _: dict = Depends(get_current_user),
):
    task = generate_embeddings.delay(body.documento_id, body.texto)
    return {"task_id": task.id, "status": "queued"}
