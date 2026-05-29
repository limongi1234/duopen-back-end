import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from postgrest.exceptions import APIError
from supabase import Client
from typing import Optional

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.obras import (
    ObraCreate,
    ObraUpdate,
    ObraResponse,
    ObraDetalheResponse,
    ObraListResponse,
)

router = APIRouter()
log = logging.getLogger(__name__)

# Colunas da tabela `obras` que servem de fallback quando a mv_obras_resumo
# (que tem os campos de risco do ML) ainda não foi populada/refrescada.
_OBRAS_FALLBACK_FIELDS = (
    "id,nome,situacao,secretaria,bairro,valor_contrato,data_prevista_fim,"
    "dias_atraso,percentual_executado,valor_aditivos,latitude,longitude"
)
# Campos de risco existem só na view; no fallback mapeamos para um proxy de atraso.
_SORT_FALLBACK_MAP = {"prob_atraso": "dias_atraso", "prob_estouro": "dias_atraso"}
_OBRAS_SORTABLE = {
    "dias_atraso",
    "percentual_executado",
    "valor_contrato",
    "data_prevista_fim",
    "nome",
}


def _listar_de_obras(
    db, *, situacao, secretaria, bairro, data_inicio, data_fim, sort, page, size, limit
) -> ObraListResponse:
    """Fallback: lista a partir da tabela `obras` (sem campos de risco do ML)."""
    query = db.table("obras").select(_OBRAS_FALLBACK_FIELDS, count="exact")
    if situacao:
        query = query.eq("situacao", situacao)
    if secretaria:
        query = query.eq("secretaria", secretaria)
    if bairro:
        query = query.eq("bairro", bairro)
    if data_inicio:
        query = query.gte("data_inicio", data_inicio.isoformat())
    if data_fim:
        query = query.lte("data_inicio", data_fim.isoformat())
    if sort:
        descending = sort.startswith("-")
        campo = sort.lstrip("+-")
        campo = _SORT_FALLBACK_MAP.get(campo, campo)
        if campo in _OBRAS_SORTABLE:
            query = query.order(campo, desc=descending)

    if limit is not None:
        result = query.limit(limit).execute()
        return ObraListResponse.build(
            data=result.data, total=result.count or len(result.data), page=1, size=limit
        )
    offset = (page - 1) * size
    result = query.range(offset, offset + size - 1).execute()
    return ObraListResponse.build(
        data=result.data, total=result.count or 0, page=page, size=size
    )


@router.get("/", response_model=ObraListResponse)
async def listar_obras(
    situacao: Optional[str] = Query(None, alias="status"),
    secretaria: Optional[str] = Query(None),
    bairro: Optional[str] = Query(None),
    nivel_risco: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(
        None, description="Filtra obras com data de início a partir desta data"
    ),
    data_fim: Optional[date] = Query(
        None, description="Filtra obras com data de início até esta data"
    ),
    sort: Optional[str] = Query(
        None,
        description="Campo de ordenação; prefixe '-' para descendente. Ex.: -prob_atraso",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    limit: Optional[int] = Query(
        None, ge=1, le=100, description="Atalho: retorna apenas os N primeiros (ignora paginação)"
    ),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    # O recorte por período usa `obras.data_inicio` (ausente na view); buscamos os
    # IDs no período e filtramos a mv_obras_resumo (que tem os campos de risco) por eles.
    ids_no_periodo: Optional[list[str]] = None
    if data_inicio or data_fim:
        periodo = db.table("obras").select("id")
        if data_inicio:
            periodo = periodo.gte("data_inicio", data_inicio.isoformat())
        if data_fim:
            periodo = periodo.lte("data_inicio", data_fim.isoformat())
        ids_no_periodo = [row["id"] for row in (periodo.execute().data or [])]
        if not ids_no_periodo:
            return ObraListResponse.build(data=[], total=0, page=page, size=limit or size)

    query = db.table("mv_obras_resumo").select("*", count="exact")  # pyright: ignore[reportArgumentType]

    if ids_no_periodo is not None:
        query = query.in_("id", ids_no_periodo)
    if situacao:
        query = query.eq("situacao", situacao)
    if secretaria:
        query = query.eq("secretaria", secretaria)
    if bairro:
        query = query.eq("bairro", bairro)
    if nivel_risco:
        query = query.eq("nivel_risco", nivel_risco)

    if sort:
        descending = sort.startswith("-")
        campo = sort.lstrip("+-")
        query = query.order(campo, desc=descending)

    try:
        if limit is not None:
            result = query.limit(limit).execute()
            return ObraListResponse.build(
                data=result.data,
                total=result.count or len(result.data),
                page=1,
                size=limit,
            )

        offset = (page - 1) * size
        result = query.range(offset, offset + size - 1).execute()
        return ObraListResponse.build(
            data=result.data,
            total=result.count or 0,
            page=page,
            size=size,
        )
    except APIError as exc:
        # 55000 = materialized view não populada (precisa de REFRESH no banco).
        if getattr(exc, "code", None) != "55000":
            raise
        log.warning(
            "mv_obras_resumo não populada; usando fallback da tabela obras. "
            "Rode REFRESH MATERIALIZED VIEW mv_obras_resumo para restaurar os campos de risco."
        )
        return _listar_de_obras(
            db,
            situacao=situacao,
            secretaria=secretaria,
            bairro=bairro,
            data_inicio=data_inicio,
            data_fim=data_fim,
            sort=sort,
            page=page,
            size=size,
            limit=limit,
        )


@router.get("/{obra_id}", response_model=ObraDetalheResponse)
async def obter_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("obras").select("*").eq("id", obra_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return result.data[0]


@router.get("/{obra_id}/contratos")
async def contratos_por_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("contratos").select("*").eq("obra_id", obra_id).execute()
    return result.data


@router.get("/{obra_id}/aditivos")
async def aditivos_por_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("aditivos").select("*").eq("obra_id", obra_id).execute()
    return result.data


@router.post("/", response_model=ObraResponse, status_code=http_status.HTTP_201_CREATED)
async def criar_obra(
    body: ObraCreate,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("obras").insert(body.model_dump()).execute()
    return result.data[0]


@router.patch("/{obra_id}", response_model=ObraResponse)
async def atualizar_obra(
    obra_id: str,
    body: ObraUpdate,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    result = db.table("obras").update(updates).eq("id", obra_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return result.data[0]


@router.delete("/{obra_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def deletar_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    db.table("obras").delete().eq("id", obra_id).execute()
