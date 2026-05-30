from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.routers.auth import get_current_user, require_perfil
from app.services.rag_service import consultar, consultar_stream, get_embeddings

router = APIRouter()


class ConsultaRequest(BaseModel):
    pergunta: str = Field(
        ..., description="Pergunta em linguagem natural sobre obras/contratos de Macaé.",
        examples=["Quais obras de nível de risco alto e de quais secretarias?"],
    )


class ConsultaResponse(BaseModel):
    resposta: str = Field(..., description="Resposta gerada pelo LLM com base nos documentos recuperados.")
    modelo: Optional[str] = Field(None, description="Modelo usado (None em caso de fallback por erro).")


class TaskEnfileirada(BaseModel):
    task_id: str
    status: str = Field(..., examples=["enqueued"])


class WarmupResponse(BaseModel):
    status: str
    modelo: str


@router.post(
    "/consulta",
    response_model=ConsultaResponse,
    summary="Consulta RAG (resposta completa)",
    description=(
        "Recupera os trechos de contratos/obras mais relevantes (busca semântica "
        "pgvector) e gera uma resposta fundamentada com o Gemini. **Perfis:** admin, gestor."
    ),
)
async def post_consulta(
    body: ConsultaRequest,
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    return await consultar(body.pergunta)


@router.get(
    "/consulta/stream",
    summary="Consulta RAG (streaming SSE)",
    description=(
        "Mesma consulta RAG, transmitindo a resposta token a token via "
        "Server-Sent Events (`text/event-stream`). Cada evento é `data: <token>\\n\\n` "
        "e o fim é `data: [DONE]\\n\\n`. **Perfis:** admin, gestor."
    ),
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def get_consulta_stream(
    pergunta: str = Query(..., description="Pergunta em linguagem natural."),
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    return StreamingResponse(
        consultar_stream(pergunta),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/embeddings/gerar",
    response_model=TaskEnfileirada,
    summary="Indexar contratos (gerar embeddings)",
    description=(
        "Dispara a task Celery que indexa os contratos em `documentos_rag`/`embeddings`, "
        "enriquecendo cada documento com o contexto da obra (nome, secretaria, bairro, "
        "nível de risco). Acompanhe pelo `task_id` em `/api/v1/ml/status/{task_id}`.\n\n"
        "- `forcar=false` (padrão): **incremental** — indexa só contratos ainda não indexados.\n"
        "- `forcar=true`: **rebuild completo** — apaga o índice e regera tudo (use após "
        "mudar o template do documento ou o modelo de embedding).\n\n"
        "**Perfil:** admin."
    ),
)
async def post_gerar_embeddings(
    forcar: bool = Query(
        False, description="Recria todo o índice do zero (rebuild). Padrão: incremental."
    ),
    _: dict = Depends(require_perfil("admin")),
):
    from app.tasks.embedding_tasks import task_gerar_embeddings

    task = task_gerar_embeddings.delay(forcar=forcar)
    return {"task_id": task.id, "status": "enqueued"}


@router.get(
    "/warmup",
    response_model=WarmupResponse,
    summary="Pré-aquecer o modelo de embedding",
    description="Carrega o modelo HF (~420MB) em memória, evitando ~30s na 1ª consulta. Requer autenticação.",
)
async def get_warmup(_: dict = Depends(get_current_user)):
    get_embeddings()
    return {"status": "ok", "modelo": get_embeddings().model_name}
