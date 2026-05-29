from typing import Any, AsyncIterator, Optional
import logging

from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import get_settings
from app.core.database import get_supabase_client
from app.schemas.ml import RAGResponse

log = logging.getLogger(__name__)

# Tabela de documentos vetorizados e função SQL de similaridade (pgvector).
DOCUMENTOS_TABLE = "documentos_rag"
MATCH_FUNCTION = "match_documentos_rag"

CHAT_MODEL = "gpt-4o-mini"

PROMPT_TEMPLATE = """Você é um assistente especializado em análise de obras públicas e \
contratos da Prefeitura de Macaé/RJ. Responda à pergunta do usuário **exclusivamente** com \
base no contexto fornecido abaixo, em português claro, técnico e objetivo.

Regras:
- Use apenas as informações do contexto. Não invente dados, valores ou prazos.
- Se a resposta não estiver no contexto, responda que não há informação suficiente nos \
documentos disponíveis.
- Quando citar valores, prazos ou fornecedores, seja específico.

Contexto:
{context}

Pergunta: {question}

Resposta:"""


class RAGService:
    """Agente de IA generativa com RAG sobre contratos e obras (LangChain + pgvector)."""

    def __init__(self) -> None:
        self.settings = get_settings()

    # ── componentes LangChain (isolados para facilitar mock/teste) ────────────
    def _embeddings(self) -> OpenAIEmbeddings:
        return OpenAIEmbeddings(
            model=self.settings.embedding_model,
            api_key=self.settings.openai_api_key,
        )

    def _llm(self, streaming: bool = False) -> ChatOpenAI:
        return ChatOpenAI(
            model=CHAT_MODEL,
            temperature=0,
            streaming=streaming,
            api_key=self.settings.openai_api_key,
        )

    def _vector_store(self) -> SupabaseVectorStore:
        return SupabaseVectorStore(
            client=get_supabase_client(),
            embedding=self._embeddings(),
            table_name=DOCUMENTOS_TABLE,
            query_name=MATCH_FUNCTION,
        )

    def _retriever(self, top_k: int = 5, obra_id: Optional[str] = None):
        search_kwargs: dict[str, Any] = {"k": top_k}
        if obra_id:
            search_kwargs["filter"] = {"id_obra": obra_id}
        return self._vector_store().as_retriever(search_kwargs=search_kwargs)

    def _prompt(self) -> PromptTemplate:
        return PromptTemplate(
            template=PROMPT_TEMPLATE, input_variables=["context", "question"]
        )

    def _build_chain(
        self, top_k: int = 5, obra_id: Optional[str] = None, streaming: bool = False
    ) -> RetrievalQA:
        return RetrievalQA.from_chain_type(
            llm=self._llm(streaming=streaming),
            chain_type="stuff",
            retriever=self._retriever(top_k=top_k, obra_id=obra_id),
            return_source_documents=True,
            chain_type_kwargs={"prompt": self._prompt()},
        )

    # ── API pública ───────────────────────────────────────────────────────────
    async def query(
        self, pergunta: str, obra_id: Optional[str] = None, top_k: int = 5
    ) -> RAGResponse:
        """Consulta RAG com resposta completa e documentos-fonte."""
        log.info("RAG query: %s... obra_id=%s", pergunta[:50], obra_id)
        chain = self._build_chain(top_k=top_k, obra_id=obra_id)
        result = await chain.ainvoke({"query": pergunta})

        fontes = [
            {
                "conteudo": getattr(doc, "page_content", ""),
                "metadata": getattr(doc, "metadata", {}),
            }
            for doc in result.get("source_documents", [])
        ]
        return RAGResponse(resposta=result.get("result", ""), fontes=fontes)

    async def stream(
        self, pergunta: str, obra_id: Optional[str] = None, top_k: int = 5
    ) -> AsyncIterator[str]:
        """Recupera contexto e transmite a resposta token a token (para SSE)."""
        log.info("RAG stream: %s... obra_id=%s", pergunta[:50], obra_id)
        retriever = self._retriever(top_k=top_k, obra_id=obra_id)
        docs = await retriever.ainvoke(pergunta)
        contexto = "\n\n".join(getattr(d, "page_content", "") for d in docs)
        prompt = self._prompt().format(context=contexto, question=pergunta)

        async for chunk in self._llm(streaming=True).astream(prompt):
            token = getattr(chunk, "content", "") or ""
            if token:
                yield token
