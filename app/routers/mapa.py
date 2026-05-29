from typing import Any, Mapping, Optional, cast

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.mapa import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONPoint,
    ObraProperties,
)

router = APIRouter()

_MAPA_FIELDS = "id, nome, status, nivel_risco, secretaria, bairro, valor_contrato, latitude, longitude"


@router.get("/", response_model=GeoJSONFeatureCollection)
async def obras_geojson(
    obra_status: Optional[str] = Query(None, alias="status"),
    nivel_risco: Optional[str] = Query(None),
    secretaria: Optional[str] = Query(None),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    query = (
        db.table("mv_mapa_obras")
        .select(_MAPA_FIELDS)
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
    )

    if obra_status:
        query = query.eq("status", obra_status)
    if nivel_risco:
        query = query.eq("nivel_risco", nivel_risco)
    if secretaria:
        query = query.eq("secretaria", secretaria)

    result = query.execute()

    features = []
    for o in result.data or []:
        row = cast(Mapping[str, Any], o)
        longitude = float(row["longitude"])
        latitude = float(row["latitude"])
        nivel_risco = row.get("nivel_risco")
        secretaria = row.get("secretaria")
        bairro = row.get("bairro")

        features.append(
            GeoJSONFeature(
                geometry=GeoJSONPoint(coordinates=[longitude, latitude]),
                properties=ObraProperties(
                    id=str(row["id"]),
                    nome=str(row["nome"]),
                    status=str(row["status"]),
                    nivel_risco=str(nivel_risco) if nivel_risco is not None else None,
                    secretaria=str(secretaria) if secretaria is not None else None,
                    bairro=str(bairro) if bairro is not None else None,
                    valor_contrato=float(row["valor_contrato"]),
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


# ── endpoint legado mantido para compatibilidade ──────────────────────────────

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
