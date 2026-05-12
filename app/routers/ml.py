from fastapi import APIRouter, Depends
from supabase import Client
from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.ml import MLAnalysisRequest, MLAnalysisResponse
from app.tasks.ml_tasks import run_ml_analysis

router = APIRouter()


@router.post("/analisar", response_model=MLAnalysisResponse)
async def disparar_analise(
    body: MLAnalysisRequest,
    _: dict = Depends(get_current_user),
):
    task = run_ml_analysis.delay(body.obra_id)
    return MLAnalysisResponse(obra_id=body.obra_id, task_id=task.id, status="queued")


@router.get("/predicoes/{obra_id}")
async def obter_predicoes(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("ml_predicoes").select("*").eq("obra_id", obra_id).execute()
    return result.data
