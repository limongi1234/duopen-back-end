from app.core.config import get_settings
from app.schemas.ml import RAGResponse
from typing import Optional
import logging

log = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.settings = get_settings()

    async def query(self, pergunta: str, obra_id: Optional[str] = None, top_k: int = 5) -> RAGResponse:
        # TODO: integrar LangChain + pgvector para busca semântica
        log.info(f"RAG query: {pergunta[:50]}... obra_id={obra_id}")
        return RAGResponse(
            resposta="Funcionalidade RAG em implementação.",
            fontes=[],
        )
