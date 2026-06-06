"""Provedor único de embeddings (Gemini), compartilhado por consulta e indexação.

Centraliza modelo, dimensão e normalização para que o vetor de uma pergunta e o
vetor de um documento indexado sejam sempre gerados do mesmo jeito — pré-requisito
da busca por similaridade. Usa a API do Gemini (sem modelo local/torch), o que
mantém a aplicação leve o bastante para rodar em hospedagem gratuita.
"""

import math

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import get_settings

# Dimensão dos vetores — casa com VECTOR(384) da tabela `embeddings` (índice
# cosseno HNSW). O gemini-embedding-001 trunca para esse tamanho via
# `output_dimensionality`, evitando migração de schema.
EMBEDDING_DIMS = 384

# Tipos de tarefa do Gemini: indexar usa DOCUMENT, consultar usa QUERY. Usar o
# par correto melhora a relevância da busca assimétrica (pergunta curta x doc).
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

# Singletons por task_type — recriar o client a cada chamada é desperdício.
_clientes: dict[str, GoogleGenerativeAIEmbeddings] = {}


def _provider(task_type: str) -> GoogleGenerativeAIEmbeddings:
    if task_type not in _clientes:
        settings = get_settings()
        _clientes[task_type] = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key,  # type: ignore[call-arg]  # alias 'api_key'
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMS,
        )
    return _clientes[task_type]


def _normalizar(vetor: list[float]) -> list[float]:
    """L2-normaliza o vetor. Ao truncar para 384 dims o Gemini não devolve vetor
    unitário; normalizamos para manter consistência com o índice cosseno e com os
    demais vetores (consulta e documentos)."""
    norma = math.sqrt(sum(v * v for v in vetor))
    if norma == 0:
        return vetor
    return [v / norma for v in vetor]


def embed_pergunta(texto: str) -> list[float]:
    """Embedding (normalizado) de uma pergunta, para busca por similaridade."""
    return _normalizar(_provider(TASK_QUERY).embed_query(texto))


def embed_documentos(textos: list[str]) -> list[list[float]]:
    """Embeddings (normalizados) de uma leva de chunks, para indexação em lote."""
    vetores = _provider(TASK_DOCUMENT).embed_documents(textos)
    return [_normalizar(v) for v in vetores]


def reset_cache() -> None:
    """Limpa os singletons — usado em testes e em troca de configuração."""
    _clientes.clear()
