from typing import Any

from fastapi import APIRouter, Depends
from supabase import Client
from app.core.database import get_supabase_client
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/resumo")
async def resumo_dashboard(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    obras = db.table("obras").select("id, status, valor_contrato").execute()
    obras_data: list[dict[str, Any]] = obras.data  # type: ignore[assignment]
    total = len(obras_data)
    em_andamento = sum(1 for o in obras_data if o["status"] == "em_andamento")
    concluidas = sum(1 for o in obras_data if o["status"] == "concluida")
    valor_total = sum(o["valor_contrato"] or 0 for o in obras_data)
    return {
        "total_obras": total,
        "em_andamento": em_andamento,
        "concluidas": concluidas,
        "valor_total_contratos": valor_total,
    }


@router.get("/eficiencia")
async def ranking_eficiencia(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("ml_predicoes").select("*").order("score_eficiencia", desc=True).limit(10).execute()
    return result.data
