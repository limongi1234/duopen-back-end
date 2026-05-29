-- ─────────────────────────────────────────────────────────────────────────────
-- RAG · Função de similaridade para o SupabaseVectorStore (LangChain)
-- Rodar no Supabase SQL Editor antes de usar /api/v1/ia/consulta.
--
-- Pré-requisitos:
--   * extensão pgvector habilitada:           CREATE EXTENSION IF NOT EXISTS vector;
--   * tabela embeddings.vetor como VECTOR(384) (modelo HF MiniLM, 384 dims)
--   * tabela documentos_rag(id, chunk_texto, metadata, id_contrato, ...)
--
-- IMPORTANTE: o LangChain SupabaseVectorStore espera as colunas de retorno
-- `id`, `content`, `metadata`, `similarity`. Por isso expomos chunk_texto AS content.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION match_documentos(
    query_embedding VECTOR(384),
    match_count     INT   DEFAULT 5,
    filter          JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id         UUID,
    content    TEXT,
    metadata   JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.chunk_texto       AS content,
        d.metadata,
        1 - (e.vetor <=> query_embedding) AS similarity
    FROM documentos_rag d
    JOIN embeddings e ON e.id_documento = d.id
    WHERE d.metadata @> filter        -- filtro opcional por metadata (jsonb)
    ORDER BY e.vetor <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Índice HNSW para acelerar a busca por similaridade (cosseno):
CREATE INDEX IF NOT EXISTS embeddings_vetor_hnsw
    ON embeddings USING hnsw (vetor vector_cosine_ops);
