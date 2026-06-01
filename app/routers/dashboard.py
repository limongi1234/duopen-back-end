from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.database import get_supabase_client, rows
from app.routers.auth import get_current_user
from app.routers.common import Periodo, get_periodo
from app.schemas.dashboard import (
    AlertaObraItem,
    DashboardResponse,
    DistribuicaoItem,
    EvolucaoMensalItem,
    IEOPStatsResponse,
    PiorObraItem,
    RankingEficienciaItem,
    SecretariaIEOP,
)

router = APIRouter()


# Mesmos limiares do frontend (features/dashboard/ieop.ts) -> consistência de classe.
def _classe_ieop(score: float) -> str:
    if score >= 80:
        return "Ótimo"
    if score >= 60:
        return "Bom"
    if score >= 40:
        return "Regular"
    if score >= 20:
        return "Ruim"
    return "Crítico"


@router.get("/", response_model=DashboardResponse, summary="Métricas globais", description="Métricas agregadas calculadas da tabela `obras`, com recorte opcional por período (`data_inicio`/`data_fim`).")
async def metricas_globais(
    periodo: Periodo = Depends(get_periodo),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    # Calculado a partir da tabela `obras` (fonte confiável e populada) em vez da
    # mv_dashboard_geral (agregado global potencialmente desatualizado), o que
    # também habilita o recorte por período.
    query = db.table("obras").select(
        "situacao,valor_contrato,percentual_executado,dias_atraso"
    )
    if periodo.data_inicio:
        query = query.gte("data_inicio", periodo.data_inicio.isoformat())
    if periodo.data_fim:
        query = query.lte("data_inicio", periodo.data_fim.isoformat())
    linhas = rows(query.limit(10000).execute())

    execucoes = [
        r["percentual_executado"] for r in linhas if r.get("percentual_executado") is not None
    ]
    return DashboardResponse(
        total_obras=len(linhas),
        valor_total=float(sum(r.get("valor_contrato") or 0 for r in linhas)),
        media_execucao_pct=round(sum(execucoes) / len(execucoes), 2) if execucoes else 0.0,
        obras_em_andamento=sum(1 for r in linhas if r.get("situacao") == "Em andamento"),
        obras_concluidas=sum(1 for r in linhas if r.get("situacao") == "Concluída"),
        obras_atrasadas=sum(1 for r in linhas if (r.get("dias_atraso") or 0) > 0),
    )


@router.get("/distribuicao-status", response_model=list[DistribuicaoItem], summary="Distribuição por status", description="Quantidade e valor total de obras agrupados por situação.")
async def distribuicao_por_status(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("situacao, valor_contrato").execute()

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"quantidade": 0, "valor_total": 0.0})
    for obra in rows(result):
        label = obra.get("situacao") or "indefinido"
        groups[label]["quantidade"] += 1
        groups[label]["valor_total"] += obra.get("valor_contrato") or 0.0

    return [DistribuicaoItem(label=k, **v) for k, v in groups.items()]


@router.get("/distribuicao-secretaria", response_model=list[DistribuicaoItem], summary="Distribuição por secretaria", description="Quantidade e valor total de obras agrupados por secretaria.")
async def distribuicao_por_secretaria(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("secretaria, valor_contrato").execute()

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"quantidade": 0, "valor_total": 0.0})
    for obra in rows(result):
        label = obra.get("secretaria") or "Não informado"
        groups[label]["quantidade"] += 1
        groups[label]["valor_total"] += obra.get("valor_contrato") or 0.0

    return [DistribuicaoItem(label=k, **v) for k, v in groups.items()]


@router.get("/evolucao", response_model=list[EvolucaoMensalItem], summary="Evolução mensal", description="Obras iniciadas e concluídas por mês.")
async def evolucao_mensal(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = db.table("mv_obras_resumo").select("data_inicio, situacao").execute()

    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"iniciadas": 0, "concluidas": 0})
    for obra in rows(result):
        raw = obra.get("data_inicio")
        if not raw:
            continue
        mes = str(raw)[:7]
        groups[mes]["iniciadas"] += 1
        if obra.get("situacao") == "Concluída":
            groups[mes]["concluidas"] += 1

    return sorted(
        [EvolucaoMensalItem(mes=k, **v) for k, v in groups.items()],
        key=lambda x: x.mes,
    )


@router.get("/alertas", response_model=list[AlertaObraItem], summary="Obras em alerta", description="Obras com nível de risco alto/crítico (limite configurável).")
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

@router.get("/resumo", summary="Resumo (legado)", description="Totais simples de obras (endpoint legado).")
async def resumo_dashboard(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    obras_data = rows(db.table("obras").select("id, situacao, valor_contrato").execute())
    total = len(obras_data)
    em_andamento = sum(1 for o in obras_data if o.get("situacao") == "Em andamento")
    concluidas = sum(1 for o in obras_data if o.get("situacao") == "Concluída")
    valor_total = sum(o.get("valor_contrato") or 0 for o in obras_data)
    return {
        "total_obras": total,
        "em_andamento": em_andamento,
        "concluidas": concluidas,
        "valor_total_contratos": valor_total,
    }


@router.get(
    "/eficiencia",
    response_model=list[RankingEficienciaItem],
    summary="Ranking de eficiência (IEOP)",
    description="Top obras por `ieop_score` (Índice de Eficiência de Obras Públicas), maior primeiro.",
)
async def ranking_eficiencia(
    limit: int = Query(10, ge=1, le=100),
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    result = (
        db.table("mv_obras_resumo")
        .select("id, nome, situacao, secretaria, valor_contrato, ieop_score, ieop_classe")
        .not_.is_("ieop_score", "null")
        .order("ieop_score", desc=True)
        .limit(limit)
        .execute()
    )
    return rows(result)


@router.get(
    "/ieop",
    response_model=IEOPStatsResponse,
    summary="Resumo IEOP do município",
    description="Média geral do IEOP, classe, distribuição por classe, ranking de secretarias e piores obras.",
)
async def ieop_stats(
    db: Client = Depends(get_supabase_client),
    _: dict = Depends(get_current_user),
):
    linhas = rows(
        db.table("obras")
        .select("id, nome, secretaria, ieop_score, ieop_classe")
        .not_.is_("ieop_score", "null")
        .execute()
    )

    scores = [r["ieop_score"] for r in linhas if r.get("ieop_score") is not None]
    media = round(sum(scores) / len(scores), 1) if scores else 0.0

    distribuicao = Counter(r["ieop_classe"] for r in linhas if r.get("ieop_classe"))

    por_secretaria: dict[str, list[float]] = defaultdict(list)
    for r in linhas:
        sec = r.get("secretaria")
        if sec and r.get("ieop_score") is not None:
            por_secretaria[sec].append(r["ieop_score"])
    ranking = [
        SecretariaIEOP(secretaria=s, media_ieop=round(sum(v) / len(v), 1))
        for s, v in por_secretaria.items()
    ]
    ranking.sort(key=lambda x: x.media_ieop, reverse=True)

    piores = sorted(
        (r for r in linhas if r.get("ieop_score") is not None),
        key=lambda r: r["ieop_score"],
    )[:5]
    piores_obras = [
        PiorObraItem(
            id=r["id"],
            nome=r["nome"],
            ieop_score=r["ieop_score"],
            ieop_classe=r.get("ieop_classe") or _classe_ieop(r["ieop_score"]),
        )
        for r in piores
    ]

    return IEOPStatsResponse(
        media_geral=media,
        classe_geral=_classe_ieop(media),
        distribuicao=dict(distribuicao),
        ranking_secretarias=ranking,
        piores_obras=piores_obras,
    )
