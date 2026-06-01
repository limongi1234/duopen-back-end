from typing import Any, Mapping, Optional, cast

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.database import get_supabase_client, rows
from app.routers.auth import get_current_user
from app.routers.common import Periodo, get_periodo
from app.schemas.mapa import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONPoint,
    ObraProperties,
)

router = APIRouter()

# secretaria e data_inicio não existem na mv_mapa_obras; o que existe está aqui.
# percentual_executado e prob_atraso existem na view; ieop_* vêm da tabela `obras`.
_MAPA_FIELDS = (
    "id, nome, situacao, nivel_risco, bairro, valor_contrato, latitude, longitude, "
    "percentual_executado, prob_atraso"
)


@router.get(
    "/",
    response_model=GeoJSONFeatureCollection,
    summary="Obras em GeoJSON",
    description="Obras geolocalizadas como FeatureCollection, com filtros por situação, nível de risco, secretaria e período.",
)
async def obras_geojson(
    obra_status: Optional[str] = Query(None, alias="status"),
    nivel_risco: Optional[str] = Query(None),
    secretaria: Optional[str] = Query(None),
    periodo: Periodo = Depends(get_periodo),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    # secretaria e período não existem na view; resolvemos os IDs na tabela `obras`.
    ids_filtrados: Optional[list[str]] = None
    if secretaria or periodo.data_inicio or periodo.data_fim:
        lookup = db.table("obras").select("id")
        if secretaria:
            lookup = lookup.eq("secretaria", secretaria)
        if periodo.data_inicio:
            lookup = lookup.gte("data_inicio", periodo.data_inicio.isoformat())
        if periodo.data_fim:
            lookup = lookup.lte("data_inicio", periodo.data_fim.isoformat())
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

    # secretaria e IEOP não estão na mv_mapa_obras; buscamos na tabela `obras`
    # pelos ids retornados (a view não expõe esses campos).
    obras_by_id: dict[str, Mapping[str, Any]] = {}
    ids = [str(cast(Mapping[str, Any], o)["id"]) for o in result.data or []]
    if ids:
        extra_rows = rows(
            db.table("obras")
            .select("id, secretaria, ieop_score, ieop_classe")
            .in_("id", ids)
            .execute()
        )
        obras_by_id = {str(r["id"]): r for r in extra_rows}

    features = []
    for o in result.data or []:
        row = cast(Mapping[str, Any], o)
        if row.get("latitude") is None or row.get("longitude") is None:
            continue
        nivel = row.get("nivel_risco")
        bairro = row.get("bairro")
        extra = obras_by_id.get(str(row["id"]), {})
        pct = row.get("percentual_executado")
        prob = row.get("prob_atraso")
        sec = extra.get("secretaria") or secretaria
        ieop_score = extra.get("ieop_score")
        ieop_classe = extra.get("ieop_classe")

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
                    # Vem da tabela `obras` (a view não tem); fallback p/ o filtro.
                    secretaria=str(sec) if sec is not None else None,
                    bairro=str(bairro) if bairro is not None else None,
                    valor_contrato=float(row.get("valor_contrato") or 0),
                    percentual_executado=float(pct) if pct is not None else None,
                    prob_atraso=float(prob) if prob is not None else None,
                    ieop_score=float(ieop_score) if ieop_score is not None else None,
                    ieop_classe=str(ieop_classe) if ieop_classe is not None else None,
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


# ── endpoint legado mantido para compatibilidade ──────────────────────────────


@router.get(
    "/obras",
    summary="Obras geolocalizadas (legado)",
    description="Lista bruta de obras com latitude/longitude (endpoint legado).",
)
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
