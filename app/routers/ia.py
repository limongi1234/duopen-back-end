from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.routers.auth import get_current_user, require_perfil
from app.services.rag_service import consultar, consultar_stream, get_embeddings
from app.tasks.celery_app import celery_app

router = APIRouter()

# Nome totalmente qualificado da task — usado na guarda de concorrência.
_EMBEDDING_TASK = "app.tasks.embedding_tasks.task_gerar_embeddings"


class ConsultaRequest(BaseModel):
    pergunta: str = Field(
        ...,
        min_length=3,
        description="Pergunta em linguagem natural sobre obras/contratos de Macaé.",
        examples=["Quais obras de nível de risco alto e de quais secretarias?"],
    )


class ConsultaResponse(BaseModel):
    resposta: str = Field(..., description="Resposta gerada pelo LLM com base nos documentos recuperados.")
    modelo: Optional[str] = Field(None, description="Modelo usado (None em caso de fallback por erro).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "resposta": "As obras de risco alto são das secretarias de Infraestrutura e Obras.",
                    "modelo": "gemini-2.5-flash-lite",
                }
            ]
        }
    )


class EmbeddingJobResponse(BaseModel):
    task_id: str = Field(..., description="ID da task Celery enfileirada.")
    status: str = Field("enqueued", description="Estado inicial da task.")
    status_url: str = Field(..., description="Endpoint para acompanhar o progresso da indexação.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "task_id": "c6e9f5e8-be5f-4a19-b99d-9cb07338c802",
                    "status": "enqueued",
                    "status_url": "/api/v1/ml/status/c6e9f5e8-be5f-4a19-b99d-9cb07338c802",
                }
            ]
        }
    )


class WarmupResponse(BaseModel):
    status: str
    modelo: str


def _indexacao_em_andamento() -> bool:
    """True se já existe uma indexação de embeddings ativa em algum worker."""
    try:
        ativos = celery_app.control.inspect(timeout=1).active() or {}
    except Exception:  # broker/worker indisponível -> não bloqueia o disparo
        return False
    return any(
        t.get("name") == _EMBEDDING_TASK
        for tarefas in ativos.values()
        for t in tarefas
    )


@router.post(
    "/consulta",
    response_model=ConsultaResponse,
    summary="Consulta RAG (resposta completa)",
    description=(
        "Recupera os trechos de contratos/obras mais relevantes (busca semântica "
        "pgvector) e gera uma resposta fundamentada com o Gemini. **Perfis:** admin, gestor."
    ),
    responses={403: {"description": "Perfil sem permissão (readonly bloqueado)."}},
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
    pergunta: str = Query(..., min_length=3, description="Pergunta em linguagem natural."),
    _: dict = Depends(require_perfil("admin", "gestor")),
):
    return StreamingResponse(
        consultar_stream(pergunta),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/embeddings/gerar",
    response_model=EmbeddingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Indexar contratos (gerar embeddings)",
    description=(
        "Enfileira a task Celery que indexa os contratos em `documentos_rag`/`embeddings`, "
        "enriquecendo cada documento com o contexto da obra (nome, secretaria, bairro, nível "
        "de risco). Retorna **202** com o `task_id` e a `status_url` para polling em "
        "`/api/v1/ml/status/{task_id}`.\n\n"
        "- `forcar=false` (padrão): **incremental** — indexa só contratos ainda não indexados.\n"
        "- `forcar=true`: **rebuild completo** — apaga o índice e regera tudo.\n\n"
        "Há **guarda de concorrência**: se já houver uma indexação em andamento, retorna **409**.\n\n"
        "**Perfil:** admin."
    ),
    responses={
        202: {"description": "Indexação enfileirada."},
        403: {
            "description": "Perfil sem permissão (apenas admin).",
            "content": {"application/json": {"example": {"detail": "Seu perfil não tem permissão para esta ação"}}},
        },
        409: {
            "description": "Já existe uma indexação em andamento.",
            "content": {"application/json": {"example": {"detail": "Já existe uma indexação de embeddings em andamento."}}},
        },
    },
)
async def post_gerar_embeddings(
    forcar: bool = Query(
        False,
        description="Recria todo o índice do zero (rebuild). Padrão: incremental.",
        openapi_examples={
            "incremental": {
                "summary": "Incremental (padrão)",
                "description": "Indexa apenas contratos ainda não indexados.",
                "value": False,
            },
            "rebuild": {
                "summary": "Rebuild completo",
                "description": "Apaga o índice e regera tudo (após mudar template/modelo).",
                "value": True,
            },
        },
    ),
    _: dict = Depends(require_perfil("admin")),
):
    if _indexacao_em_andamento():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma indexação de embeddings em andamento.",
        )

    from app.tasks.embedding_tasks import task_gerar_embeddings

    task = task_gerar_embeddings.delay(forcar=forcar)
    return EmbeddingJobResponse(
        task_id=task.id,
        status="enqueued",
        status_url=f"/api/v1/ml/status/{task.id}",
    )


@router.get(
    "/warmup",
    response_model=WarmupResponse,
    summary="Pré-aquecer o modelo de embedding",
    description="Carrega o modelo HF (~420MB) em memória, evitando ~30s na 1ª consulta. Requer autenticação.",
)
async def get_warmup(_: dict = Depends(get_current_user)):
    get_embeddings()
    return {"status": "ok", "modelo": get_embeddings().model_name}
