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


class ObraCreate(BaseModel):
    """Criação manual de obra (obras normalmente vêm do ETL de coleta).

    Espelha colunas reais da tabela `obras`; só `nome` é obrigatório.
    """

    nome: str
    objeto: Optional[str] = None
    situacao: Optional[str] = None
    tipo: Optional[str] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    valor_contrato: Optional[float] = None
    data_inicio: Optional[date] = None
    data_prevista_fim: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ObraUpdate(BaseModel):
    nome: Optional[str] = None
    objeto: Optional[str] = None
    situacao: Optional[str] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    valor_contrato: Optional[float] = None
    data_prevista_fim: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ObraDetalheResponse(ObraColetaFields, ObraIEOPFields):
    """Detalhe da obra — espelha a tabela `obras` (campos nullable, exceto id/nome).

    Inclui os campos de coleta (mixin) e de IEOP/ML (mixin).
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    objeto: Optional[str] = None
    situacao: Optional[str] = None
    tipo: Optional[str] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    endereco: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    valor_contrato: Optional[float] = None
    valor_aditivos: Optional[float] = None
    valor_final: Optional[float] = None
    percentual_executado: Optional[float] = None
    dias_atraso: Optional[int] = None
    qtd_aditivos: Optional[int] = None
    area_m2: Optional[float] = None
    data_inicio: Optional[str] = None
    data_prevista_fim: Optional[str] = None
    data_conclusao: Optional[str] = None
    fonte_origem: Optional[str] = None
    criado_em: Optional[str] = None
    atualizado_em: Optional[str] = None


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
