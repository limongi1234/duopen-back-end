import math
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date


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


class ObraResponse(ObraBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: str


class ObraDetalheResponse(ObraResponse):
    pass


class ObraResumoResponse(BaseModel):
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
