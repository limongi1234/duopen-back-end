import logging
from typing import AsyncGenerator

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import get_settings
from app.core.database import get_supabase_client

log = logging.getLogger("services.rag")

# Função SQL criada na migration de RAG (ver scripts/sql/rag_match_function.sql).
MATCH_FUNCTION = "match_documentos"
DOCUMENTOS_TABLE = "documentos_rag"

# ── Singletons — inicializados uma vez (evita recarregar o modelo ~420MB) ──────
_embeddings: HuggingFaceEmbeddings | None = None
_llm: ChatGoogleGenerativeAI | None = None
_vector_store: SupabaseVectorStore | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        settings = get_settings()
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
            cache_folder="/app/.cache/huggingface",
        )
    return _embeddings


def get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=settings.rag_temperature,
            convert_system_message_to_human=True,
        )
    return _llm


def get_vector_store() -> SupabaseVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = SupabaseVectorStore(
            client=get_supabase_client(),
            embedding=get_embeddings(),
            table_name=DOCUMENTOS_TABLE,
            query_name=MATCH_FUNCTION,
        )
    return _vector_store


# ── Prompt em português contextualizado para obras de Macaé ────────────────────
PROMPT = ChatPromptTemplate.from_template(
    """Você é um assistente especializado em análise de obras públicas do \
município de Macaé, Rio de Janeiro.

Responda à pergunta do gestor com base EXCLUSIVAMENTE nos trechos de contratos \
e dados de obras fornecidos abaixo. Se a informação não estiver no contexto, \
diga claramente que não encontrou dados suficientes para responder. Nunca \
invente dados ou números.

Responda em português brasileiro, de forma clara e objetiva. Use dados e \
valores reais quando disponíveis no contexto.

CONTEXTO:
{context}

PERGUNTA:
{question}

RESPOSTA:"""
)


def _formatar_contexto(docs) -> str:
    return "\n\n---\n\n".join(d.page_content for d in docs)


async def consultar(pergunta: str) -> dict:
    """Executa consulta RAG e retorna a resposta completa."""
    try:
        top_k = get_settings().rag_top_k
        retriever = get_vector_store().as_retriever(
            search_type="similarity", search_kwargs={"k": top_k}
        )
        chain = (
            {"context": retriever | _formatar_contexto, "question": RunnablePassthrough()}
            | PROMPT
            | get_llm()
            | StrOutputParser()
        )
        resposta = await chain.ainvoke(pergunta)
        return {"resposta": resposta, "modelo": get_settings().llm_model}
    except Exception as e:
        log.error("Erro RAG consultar(): %s", e)
        return {
            "resposta": "Não foi possível processar sua consulta. Tente novamente.",
            "modelo": None,
        }


async def consultar_stream(pergunta: str) -> AsyncGenerator[str, None]:
    """Executa consulta RAG com streaming da resposta (SSE)."""
    try:
        top_k = get_settings().rag_top_k
        docs = get_vector_store().similarity_search(pergunta, k=top_k)
        contexto = _formatar_contexto(docs)
        msgs = PROMPT.format_messages(context=contexto, question=pergunta)

        async for chunk in get_llm().astream(msgs):
            if chunk.content:
                yield f"data: {chunk.content}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        log.error("Erro RAG streaming: %s", e)
        yield "data: Erro ao processar a consulta.\n\n"
        yield "data: [DONE]\n\n"
