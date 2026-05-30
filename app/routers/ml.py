from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user, require_perfil
from app.schemas.ml import (
    MLAnalysisRequest,
    MLAnalysisResponse,
    PredicaoResponse,
    TaskStatusResponse,
)
from app.services.ml_service import MLService
from app.tasks.celery_app import celery_app
from app.tasks.ml_tasks import run_ml_analysis, run_ml_retraining

router = APIRouter()


@router.get(
    "/predicoes",
    response_model=list[PredicaoResponse],
    summary="Listar predições de risco",
    description="Lista as predições (`prob_atraso`, `prob_estouro`, `nivel_risco`), com filtro opcional por nível de risco.",
)
async def listar_predicoes(
    nivel_risco: Optional[str] = Query(
        None, description="Filtra por nível de risco (ex.: baixo, medio, alto, critico)"
    ),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    return MLService(db).listar_predicoes(nivel_risco=nivel_risco)


@router.get(
    "/predicoes/{obra_id}",
    response_model=PredicaoResponse,
    summary="Predição de risco de uma obra",
    description="Retorna a predição de risco (atraso/estouro) de uma obra. **404** se não houver predição.",
)
async def obter_predicao(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    predicao = MLService(db).get_predicao(obra_id)
    if predicao is None:
        raise HTTPException(status_code=404, detail="Predição não encontrada para a obra")
    return predicao


@router.post(
    "/reprocessar",
    response_model=TaskStatusResponse,
    summary="Re-treinar o modelo (admin)",
    description="Dispara a task Celery de re-treinamento do modelo de risco (XGBoost). **Perfil:** admin.",
)
async def reprocessar_modelo(_: dict = Depends(require_perfil("admin"))):
    task = run_ml_retraining.delay()
    return TaskStatusResponse(task_id=task.id, status="queued")


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Status de uma task assíncrona",
    description="Consulta o estado de uma task Celery (re-treino, embeddings, etc.) pelo `task_id`.",
)
async def status_reprocessamento(
    task_id: str,
    _: dict = Depends(get_current_user),
):
    result = celery_app.AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        resultado=result.result if result.successful() else None,
    )


@router.post(
    "/analisar",
    response_model=MLAnalysisResponse,
    summary="Análise de risco sob demanda (compat)",
    description="Enfileira a análise de risco de uma obra específica. Endpoint legado mantido por compatibilidade.",
)
async def disparar_analise(
    body: MLAnalysisRequest,
    _: dict = Depends(get_current_user),
):
    task = run_ml_analysis.delay(body.obra_id)
    return MLAnalysisResponse(obra_id=body.obra_id, task_id=task.id, status="queued")
