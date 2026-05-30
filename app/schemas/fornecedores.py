import math
from typing import Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class FornecedorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cnpj: str
    # Aceita `razao_social` (da view) ou `nome` na entrada; serializa como `nome`.
    nome: str = Field(validation_alias=AliasChoices("razao_social", "nome"))
    total_contratos: int
    valor_total: float
    taxa_aditivo: Optional[float] = None
    media_prob_atraso: Optional[float] = None
    obras_concluidas: Optional[int] = None
    obras_em_andamento: Optional[int] = None


class FornecedorRankingResponse(BaseModel):
    items: list[FornecedorResponse]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, data: list, total: int, page: int, size: int) -> "FornecedorRankingResponse":
        pages = math.ceil(total / size) if total > 0 else 1
        return cls(items=data, total=total, page=page, size=size, pages=pages)
