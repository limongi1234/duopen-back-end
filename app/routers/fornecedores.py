from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.core.database import get_supabase_client
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/")
async def listar_fornecedores(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("fornecedores").select("*").execute()
    return result.data


@router.get("/{fornecedor_id}")
async def obter_fornecedor(
    fornecedor_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("fornecedores").select("*").eq("id", fornecedor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    return result.data[0]
