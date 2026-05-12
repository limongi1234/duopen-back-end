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


class ObraResponse(ObraBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: str
