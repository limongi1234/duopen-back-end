from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.database import get_supabase_client
from app.routers.auth import get_current_user
from app.schemas.dashboard import (
    AlertaObraItem,
    DashboardResponse,
    DistribuicaoItem,
    EvolucaoMensalItem,
)

router = APIRouter()


@router.get("/", response_model=DashboardResponse)
async def metricas_globais(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_dashboard_geral").select("*").execute()
    if not result.data:
        raise HTTPException(status_code=503, detail="Dados do dashboard indisponíveis")
    return result.data[0]


@router.get("/distribuicao-status", response_model=list[DistribuicaoItem])
async def distribuicao_por_status(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("status, valor_contrato").execute()

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"quantidade": 0, "valor_total": 0.0})
    for obra in result.data:
        label = obra.get("status") or "indefinido"
        groups[label]["quantidade"] += 1
        groups[label]["valor_total"] += obra.get("valor_contrato") or 0.0

    return [DistribuicaoItem(label=k, **v) for k, v in groups.items()]


@router.get("/distribuicao-secretaria", response_model=list[DistribuicaoItem])
async def distribuicao_por_secretaria(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("secretaria, valor_contrato").execute()

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"quantidade": 0, "valor_total": 0.0})
    for obra in result.data:
        label = obra.get("secretaria") or "Não informado"
        groups[label]["quantidade"] += 1
        groups[label]["valor_total"] += obra.get("valor_contrato") or 0.0

    return [DistribuicaoItem(label=k, **v) for k, v in groups.items()]


@router.get("/evolucao", response_model=list[EvolucaoMensalItem])
async def evolucao_mensal(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("data_inicio, status").execute()

    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"iniciadas": 0, "concluidas": 0})
    for obra in result.data:
        raw = obra.get("data_inicio")
        if not raw:
            continue
        mes = str(raw)[:7]
        groups[mes]["iniciadas"] += 1
        if obra.get("status") == "concluida":
            groups[mes]["concluidas"] += 1

    return sorted(
        [EvolucaoMensalItem(mes=k, **v) for k, v in groups.items()],
        key=lambda x: x.mes,
    )


@router.get("/alertas", response_model=list[AlertaObraItem])
async def obras_em_alerta(
    limit: int = Query(20, ge=1, le=100),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("mv_obras_resumo")
        .select("id, nome, nivel_risco, secretaria, bairro, valor_contrato, data_prevista_fim")
        .in_("nivel_risco", ["alto", "critico"])
        .order("nivel_risco", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


# ── endpoints legados mantidos para compatibilidade ───────────────────────────

@router.get("/resumo")
async def resumo_dashboard(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    obras = db.table("obras").select("id, status, valor_contrato").execute()
    obras_data: list[dict[str, Any]] = obras.data  # type: ignore[assignment]
    total = len(obras_data)
    em_andamento = sum(1 for o in obras_data if o["status"] == "em_andamento")
    concluidas = sum(1 for o in obras_data if o["status"] == "concluida")
    valor_total = sum(o["valor_contrato"] or 0 for o in obras_data)
    return {
        "total_obras": total,
        "em_andamento": em_andamento,
        "concluidas": concluidas,
        "valor_total_contratos": valor_total,
    }


@router.get("/eficiencia")
async def ranking_eficiencia(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("ml_predicoes").select("*").order("score_eficiencia", desc=True).limit(10).execute()
    return result.data
