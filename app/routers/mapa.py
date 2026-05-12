from fastapi import APIRouter, Depends
from supabase import Client
from app.core.database import get_supabase_client
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/obras")
async def obras_geolocalizadas(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("obras")
        .select("id, nome, status, latitude, longitude, valor_contrato")
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .execute()
    )
    return result.data
