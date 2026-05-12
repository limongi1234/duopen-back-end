from pydantic import BaseModel
from typing import Optional


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
