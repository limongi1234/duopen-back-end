import math
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ObraColetaFields(BaseModel):
    """Campos adicionais produzidos pelo ETL de coleta (PRs #5/#6/#9).

    Todos **nullable**: só vêm preenchidos no grupo legado e após as migrations +
    pipeline. Tratar ausência como "não informado".
    """

    cnpj_executora: Optional[str] = None
    num_contrato: Optional[str] = None
    num_licitacao: Optional[str] = None
    ano_conclusao: Optional[int] = None  # ano (ex.: 2014), não data
    percentual_executado_financeiro: Optional[float] = None


class ObraIEOPFields(BaseModel):
    """Resultado do modelo de eficiência (IEOP) gravado pelo duopen-ml em `obras`.

    Todos nullable. `ieop_score` é 0–100; `ieop_classe` é categórico
    (ex.: Ótimo/Bom/Regular); os demais `ieop_*` são componentes (0–100).
    """

    ieop_score: Optional[float] = None
    ieop_classe: Optional[str] = None
    ieop_custo: Optional[float] = None
    ieop_atraso: Optional[float] = None
    ieop_recorrencia: Optional[float] = None
    ieop_execucao: Optional[float] = None
    ieop_calculado_em: Optional[str] = None
    tipo_sinapi: Optional[str] = None


class ObraBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    valor_contrato: float
    data_inicio: date
    data_prevista_fim: date
    status: str = "em_andamento"
    municipio: str = "Macaé"
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    nivel_risco: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ObraCreate(ObraBase):
    pass


class ObraUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    valor_contrato: Optional[float] = None
    status: Optional[str] = None
    data_prevista_fim: Optional[date] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    nivel_risco: Optional[str] = None


class ObraResponse(ObraBase, ObraColetaFields, ObraIEOPFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: str


class ObraDetalheResponse(ObraResponse):
    pass


class ObraResumoResponse(ObraColetaFields, ObraIEOPFields):
    """Item da listagem, espelhando a view `mv_obras_resumo`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    situacao: Optional[str] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    nivel_risco: Optional[str] = None
    valor_contrato: Optional[float] = None
    data_prevista_fim: Optional[str] = None
    dias_atraso: Optional[int] = None
    percentual_executado: Optional[float] = None
    prob_atraso: Optional[float] = None
    prob_estouro: Optional[float] = None
    qtd_aditivos: Optional[int] = None
    valor_aditivos: Optional[float] = None
    valor_total_aditivos: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ObraListResponse(BaseModel):
    items: list[ObraResumoResponse]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, data: list, total: int, page: int, size: int) -> "ObraListResponse":
        pages = math.ceil(total / size) if total > 0 else 1
        return cls(items=data, total=total, page=page, size=size, pages=pages)
