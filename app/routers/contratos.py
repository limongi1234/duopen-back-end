from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/", summary="Listar contratos", description="Lista todos os contratos.")
async def listar_contratos(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("contratos").select("*").execute()
    return result.data


@router.get(
    "/{contrato_id}",
    summary="Detalhe do contrato",
    description="Retorna um contrato por id. **404** se não encontrado.",
)
async def obter_contrato(
    contrato_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("contratos").select("*").eq("id", contrato_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return result.data[0]


@router.get(
    "/obra/{obra_id}",
    summary="Contratos por obra",
    description="Lista os contratos vinculados a uma obra (`id_obra`).",
)
async def contratos_por_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("contratos").select("*").eq("id_obra", obra_id).execute()
    return result.data
