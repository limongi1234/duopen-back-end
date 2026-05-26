from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
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


@router.get("/", response_model=ObraListResponse)
async def listar_obras(
    obra_status: Optional[str] = Query(None, alias="status"),
    secretaria: Optional[str] = Query(None),
    bairro: Optional[str] = Query(None),
    nivel_risco: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    query = db.table("mv_obras_resumo").select("*", count="exact") # pyright: ignore[reportArgumentType]

    if obra_status:
        query = query.eq("status", obra_status)
    if secretaria:
        query = query.eq("secretaria", secretaria)
    if bairro:
        query = query.eq("bairro", bairro)
    if nivel_risco:
        query = query.eq("nivel_risco", nivel_risco)

    offset = (page - 1) * size
    result = query.range(offset, offset + size - 1).execute()

    return ObraListResponse.build(
        data=result.data,
        total=result.count or 0,
        page=page,
        size=size,
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
