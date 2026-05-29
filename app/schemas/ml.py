from pydantic import BaseModel, ConfigDict
from typing import Any, Optional


class MLAnalysisRequest(BaseModel):
    obra_id: str


class MLAnalysisResponse(BaseModel):
    obra_id: str
    task_id: str
    status: str


class MLPrediction(BaseModel):
    obra_id: str
    risco_atraso: float
    risco_sobrecusto: float
    score_eficiencia: float
    recomendacoes: list[str]


class EmbeddingRequest(BaseModel):
    documento_id: str
    texto: str


class RAGQuery(BaseModel):
    pergunta: str
    obra_id: Optional[str] = None
    top_k: int = 5


class RAGResponse(BaseModel):
    resposta: str
    fontes: list[dict]


class PredicaoResponse(BaseModel):
    """Predição de risco de uma obra (tabela `predicoes`)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    id_obra: str
    prob_atraso: Optional[float] = None
    prob_estouro: Optional[float] = None
    nivel_risco: Optional[str] = None
    modelo_versao: Optional[str] = None
    atualizado_em: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Status de uma task assíncrona (Celery)."""

    task_id: str
    status: str
    resultado: Optional[Any] = None
