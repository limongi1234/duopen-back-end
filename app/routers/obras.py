from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.obras import ObraCreate, ObraUpdate, ObraResponse

router = APIRouter()


@router.get("/", response_model=list[ObraResponse])
async def listar_obras(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("obras").select("*").execute()
    return result.data


@router.get("/{obra_id}", response_model=ObraResponse)
async def obter_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("obras").select("*").eq("id", obra_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return result.data[0]


@router.post("/", response_model=ObraResponse, status_code=status.HTTP_201_CREATED)
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


@router.delete("/{obra_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_obra(
    obra_id: str,
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    db.table("obras").delete().eq("id", obra_id).execute()
