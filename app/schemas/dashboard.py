from pydantic import BaseModel
from typing import Optional


class DashboardResponse(BaseModel):
    total_obras: int
    valor_total: float
    media_execucao_pct: float
    obras_em_andamento: int
    obras_concluidas: int
    obras_atrasadas: int


class DistribuicaoItem(BaseModel):
    label: str
    quantidade: int
    valor_total: float


class EvolucaoMensalItem(BaseModel):
    mes: str
    iniciadas: int
    concluidas: int


class AlertaObraItem(BaseModel):
    id: str
    nome: str
    nivel_risco: str
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    valor_contrato: float
    data_prevista_fim: str


class RankingEficienciaItem(BaseModel):
    id: str
    nome: str
    ieop_score: float
    ieop_classe: Optional[str] = None
    situacao: Optional[str] = None
    secretaria: Optional[str] = None
    valor_contrato: Optional[float] = None


class SecretariaIEOP(BaseModel):
    secretaria: str
    media_ieop: float


class PiorObraItem(BaseModel):
    id: str
    nome: str
    ieop_score: float
    ieop_classe: str


class IEOPStatsResponse(BaseModel):
    """Resumo IEOP do município (GET /api/v1/dashboard/ieop)."""

    media_geral: float
    classe_geral: str
    distribuicao: dict[str, int]
    ranking_secretarias: list[SecretariaIEOP]
    piores_obras: list[PiorObraItem]
