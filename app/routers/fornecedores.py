from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.types import CountMethod
from supabase import Client

from app.core.database import first, get_supabase_client, rows
from app.routers.auth import get_current_user
from app.schemas.fornecedores import FornecedorRankingResponse, FornecedorResponse

router = APIRouter()


@router.get(
    "/",
    response_model=FornecedorRankingResponse,
    summary="Ranking de fornecedores",
    description="Ranking por nº de contratos, com filtros opcionais por taxa de aditivo e prob. média de atraso, e paginação.",
)
async def ranking_fornecedores(
    taxa_aditivo_max: Optional[float] = Query(None, ge=0, le=1),
    media_prob_atraso_max: Optional[float] = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    query = db.table("mv_fornecedores_ranking").select("*", count=CountMethod.exact)

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
        data=rows(result),
        total=result.count or 0,
        page=page,
        size=size,
    )


@router.get(
    "/{cnpj}/obras",
    summary="Contratos do fornecedor",
    description="Lista os contratos de um fornecedor (identificado por CNPJ).",
)
async def obras_do_fornecedor(
    cnpj: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    # cnpj -> id do fornecedor (tabela `fornecedores`) -> contratos por id_fornecedor.
    fornecedor = first(db.table("fornecedores").select("id").eq("cnpj", cnpj).execute())
    if not fornecedor:
        return []
    result = (
        db.table("contratos")
        .select("id, numero, objeto, situacao, valor_global, valor_final, id_obra")
        .eq("id_fornecedor", fornecedor["id"])
        .execute()
    )
    return rows(result)


@router.get(
    "/{cnpj}",
    response_model=FornecedorResponse,
    summary="Perfil do fornecedor",
    description="Retorna o perfil/ranking de um fornecedor por CNPJ. **404** se não encontrado.",
)
async def perfil_fornecedor(
    cnpj: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    fornecedor = first(
        db.table("mv_fornecedores_ranking").select("*").eq("cnpj", cnpj).execute()
    )
    if fornecedor is None:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    return fornecedor
