import logging
from typing import Any, AsyncGenerator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import get_settings
from app.core.database import get_supabase_client, rows

log = logging.getLogger("services.rag")

# Função SQL de similaridade (ver scripts/sql/rag_match_function.sql).
MATCH_FUNCTION = "match_documentos"

# ── Singletons — inicializados uma vez (evita recarregar o modelo ~420MB) ──────
_embeddings: HuggingFaceEmbeddings | None = None
_llm: ChatGoogleGenerativeAI | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        settings = get_settings()
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
            cache_folder=settings.hf_cache_folder,
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


def buscar_documentos(pergunta: str, top_k: int) -> list[dict[str, Any]]:
    """Busca semântica via RPC pgvector (evita o SupabaseVectorStore, incompatível
    com a versão atual do postgrest). Retorna linhas {content, metadata, similarity}."""
    vetor = get_embeddings().embed_query(pergunta)
    result = get_supabase_client().rpc(
        MATCH_FUNCTION, {"query_embedding": vetor, "match_count": top_k}
    ).execute()
    return rows(result)


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


def _formatar_contexto(docs: list[dict]) -> str:
    return "\n\n---\n\n".join(d.get("content", "") for d in docs)


def _texto_do_chunk(content: Any) -> str:
    """Normaliza o conteúdo do Gemini (str ou lista de partes) para texto."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    return str(content)


async def consultar(pergunta: str) -> dict:
    """Executa consulta RAG e retorna a resposta completa."""
    try:
        top_k = get_settings().rag_top_k
        contexto = _formatar_contexto(buscar_documentos(pergunta, top_k))
        chain = PROMPT | get_llm() | StrOutputParser()
        resposta = await chain.ainvoke({"context": contexto, "question": pergunta})
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
        contexto = _formatar_contexto(buscar_documentos(pergunta, top_k))
        msgs = PROMPT.format_messages(context=contexto, question=pergunta)

        async for chunk in get_llm().astream(msgs):
            texto = _texto_do_chunk(chunk.content)
            if texto:
                yield f"data: {texto}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        log.error("Erro RAG streaming: %s", e)
        yield "data: Erro ao processar a consulta.\n\n"
        yield "data: [DONE]\n\n"
