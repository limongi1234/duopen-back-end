from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.fornecedores import FornecedorResponse, FornecedorRankingResponse

router = APIRouter()


@router.get("/", response_model=FornecedorRankingResponse)
async def ranking_fornecedores(
    taxa_aditivo_max: Optional[float] = Query(None, ge=0, le=1),
    media_prob_atraso_max: Optional[float] = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    query = db.table("mv_fornecedores_ranking").select("*", count="exact")

    if taxa_aditivo_max is not None:
        query = query.lte("taxa_aditivo", taxa_aditivo_max)
    if media_prob_atraso_max is not None:
        query = query.lte("media_prob_atraso", media_prob_atraso_max)

    offset = (page - 1) * size
    result = (
        query
        .order("total_contratos", desc=True)
        .range(offset, offset + size - 1)
        .execute()
    )

    return FornecedorRankingResponse.build(
        data=result.data,
        total=result.count or 0,
        page=page,
        size=size,
    )


@router.get("/{cnpj}/obras")
async def obras_do_fornecedor(
    cnpj: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("contratos")
        .select("obra_id, obras(id, nome, status, valor_contrato, data_prevista_fim)")
        .eq("cnpj_fornecedor", cnpj)
        .execute()
    )
    return result.data


@router.get("/{cnpj}", response_model=FornecedorResponse)
async def perfil_fornecedor(
    cnpj: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("mv_fornecedores_ranking")
        .select("*")
        .eq("cnpj", cnpj)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    return result.data[0]
