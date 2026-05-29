import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.routers.auth import require_perfil
from app.schemas.ml import EmbeddingRequest, RAGQuery, RAGResponse
from app.services.rag_service import RAGService
from app.tasks.embedding_tasks import generate_embeddings

router = APIRouter()


@router.post("/consulta", response_model=RAGResponse)
async def consultar(
    body: RAGQuery,
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    return await RAGService().query(body.pergunta, obra_id=body.obra_id, top_k=body.top_k)


@router.get("/consulta/stream")
async def consultar_stream(
    pergunta: str = Query(..., min_length=1, description="Pergunta em linguagem natural"),
    obra_id: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    service = RAGService()

    async def event_stream():
        async for token in service.stream(pergunta, obra_id=obra_id, top_k=top_k):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/embeddings/gerar")
async def gerar_embeddings(
    body: EmbeddingRequest,
    _: dict = Depends(require_perfil("admin")),
):
    task = generate_embeddings.delay(body.documento_id, body.texto)
    return {"task_id": task.id, "status": "queued"}
