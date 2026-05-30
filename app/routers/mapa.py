from datetime import date
from typing import Any, Mapping, Optional, cast

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.database import get_supabase_client, rows
from app.routers.auth import get_current_user
from app.schemas.mapa import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONPoint,
    ObraProperties,
)

router = APIRouter()

# secretaria e data_inicio não existem na mv_mapa_obras; o que existe está aqui.
_MAPA_FIELDS = "id, nome, situacao, nivel_risco, bairro, valor_contrato, latitude, longitude"


@router.get("/", response_model=GeoJSONFeatureCollection, summary="Obras em GeoJSON", description="Obras geolocalizadas como FeatureCollection, com filtros por situação, nível de risco, secretaria e período.")
async def obras_geojson(
    obra_status: Optional[str] = Query(None, alias="status"),
    nivel_risco: Optional[str] = Query(None),
    secretaria: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(
        None, description="Filtra obras com data de início a partir desta data"
    ),
    data_fim: Optional[date] = Query(
        None, description="Filtra obras com data de início até esta data"
    ),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    # secretaria e período não existem na view; resolvemos os IDs na tabela `obras`.
    ids_filtrados: Optional[list[str]] = None
    if secretaria or data_inicio or data_fim:
        lookup = db.table("obras").select("id")
        if secretaria:
            lookup = lookup.eq("secretaria", secretaria)
        if data_inicio:
            lookup = lookup.gte("data_inicio", data_inicio.isoformat())
        if data_fim:
            lookup = lookup.lte("data_inicio", data_fim.isoformat())
        ids_filtrados = [row["id"] for row in rows(lookup.execute())]
        if not ids_filtrados:
            return GeoJSONFeatureCollection(features=[])

    query = (
        db.table("mv_mapa_obras")
        .select(_MAPA_FIELDS)
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
    )

    if ids_filtrados is not None:
        query = query.in_("id", ids_filtrados)
    if obra_status:
        query = query.eq("situacao", obra_status)
    if nivel_risco:
        query = query.eq("nivel_risco", nivel_risco)

    result = query.execute()

    features = []
    for o in result.data or []:
        row = cast(Mapping[str, Any], o)
        if row.get("latitude") is None or row.get("longitude") is None:
            continue
        nivel = row.get("nivel_risco")
        bairro = row.get("bairro")

        features.append(
            GeoJSONFeature(
                geometry=GeoJSONPoint(
                    coordinates=[float(row["longitude"]), float(row["latitude"])]
                ),
                properties=ObraProperties(
                    id=str(row["id"]),
                    nome=str(row["nome"]),
                    status=str(row.get("situacao") or "Indefinido"),
                    nivel_risco=str(nivel) if nivel is not None else None,
                    # Não está na view; ecoa o filtro quando informado.
                    secretaria=secretaria,
                    bairro=str(bairro) if bairro is not None else None,
                    valor_contrato=float(row.get("valor_contrato") or 0),
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


# ── endpoint legado mantido para compatibilidade ──────────────────────────────

@router.get("/obras", summary="Obras geolocalizadas (legado)", description="Lista bruta de obras com latitude/longitude (endpoint legado).")
async def obras_geolocalizadas(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("obras")
        .select("id, nome, situacao, latitude, longitude, valor_contrato")
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .execute()
    )
    return result.data
