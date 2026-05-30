import logging
from typing import Any, Optional

from postgrest.exceptions import APIError

from app.tasks.celery_app import celery_app, backoff_countdown
from app.core.config import get_settings
from app.core.database import get_supabase_client

log = logging.getLogger("tasks.embedding")

CHUNK_SIZE = 512   # caracteres por chunk
CHUNK_OVERLAP = 50  # sobreposição entre chunks
_UUID_ZERO = "00000000-0000-0000-0000-000000000000"  # filtro "match-all" para delete


def _linha(rotulo: str, valor: Any) -> Optional[str]:
    return f"{rotulo}: {valor}" if valor not in (None, "") else None


def _montar_texto(contrato: dict, obra: Optional[dict]) -> str:
    """Texto indexável do contrato, enriquecido com o contexto da obra vinculada."""
    linhas = [
        _linha("Objeto do contrato", contrato.get("objeto")),
        _linha("Modalidade", contrato.get("modalidade")),
        _linha("Situação do contrato", contrato.get("situacao")),
        _linha("Valor global (R$)", contrato.get("valor_global")),
        _linha("Valor final (R$)", contrato.get("valor_final")),
    ]
    if obra:
        linhas += [
            _linha("Obra vinculada", obra.get("nome")),
            _linha("Secretaria", obra.get("secretaria")),
            _linha("Bairro", obra.get("bairro")),
            _linha("Situação da obra", obra.get("situacao")),
            _linha("Nível de risco (ML)", obra.get("nivel_risco")),
            _linha("Probabilidade de atraso", obra.get("prob_atraso")),
        ]
    return "\n".join(linha for linha in linhas if linha)


def _metadata(contrato: dict, obra: Optional[dict]) -> dict:
    obra = obra or {}
    return {
        "id_contrato": contrato["id"],
        "id_obra": contrato.get("id_obra"),
        "modalidade": contrato.get("modalidade"),
        "situacao_contrato": contrato.get("situacao"),
        "obra": obra.get("nome"),
        "secretaria": obra.get("secretaria"),
        "nivel_risco": obra.get("nivel_risco"),
    }


def _vetor_para_pgvector(vetor: list[float]) -> str:
    """pgvector aceita o literal textual '[v1,v2,...]'."""
    return "[" + ",".join(str(v) for v in vetor) + "]"


def _carregar_obras(client) -> dict[str, dict]:
    """Lookup `id_obra -> resumo` para enriquecimento. Resiliente: se a view
    estiver stale/não-populada, segue sem enriquecer (degrada com elegância)."""
    try:
        linhas = (
            client.table("mv_obras_resumo")
            .select("id,nome,secretaria,bairro,nivel_risco,prob_atraso,situacao")
            .execute()
            .data
            or []
        )
        return {o["id"]: o for o in linhas}
    except APIError as exc:
        log.warning("Enriquecimento indisponível (mv_obras_resumo): %s", exc)
        return {}


@celery_app.task(bind=True, max_retries=3)
def task_gerar_embeddings(self, forcar: bool = False) -> dict:
    """Indexa em `documentos_rag`/`embeddings` os contratos ainda sem embedding,
    enriquecendo cada documento com o contexto da obra vinculada (nome, secretaria,
    bairro, nível de risco do ML).

    Args:
        forcar: quando True, apaga todo o índice e regera do zero (rebuild
            completo). Use após mudar o template do documento ou o modelo de
            embedding. Quando False (padrão), é incremental: só indexa contratos
            ainda não presentes em `documentos_rag`.

    Modelo: paraphrase-multilingual-MiniLM-L12-v2 (384 dims).
    """
    try:
        # Imports pesados (torch/transformers) ficam locais para não onerar o import do módulo.
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        client = get_supabase_client()
        model = SentenceTransformer(settings.embedding_model)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

        if forcar:
            # Rebuild completo: apaga na ordem da FK (embeddings -> documentos_rag).
            log.warning("Reindexação forçada: apagando índice RAG existente")
            client.table("embeddings").delete().neq("id", _UUID_ZERO).execute()
            client.table("documentos_rag").delete().neq("id", _UUID_ZERO).execute()
            ja_indexados: set = set()
        else:
            ja_indexados = {
                r["id_contrato"]
                for r in (client.table("documentos_rag").select("id_contrato").execute().data or [])
                if r.get("id_contrato")
            }
        contratos = (
            client.table("contratos")
            .select("id,id_obra,objeto,modalidade,situacao,valor_global,valor_final")
            .execute()
            .data
            or []
        )
        obras_por_id = _carregar_obras(client)

        total_chunks = 0
        for contrato in contratos:
            if contrato["id"] in ja_indexados:
                continue
            obra = obras_por_id.get(contrato.get("id_obra"))
            texto = _montar_texto(contrato, obra)
            if not texto.strip():
                continue

            metadata = _metadata(contrato, obra)
            for chunk in splitter.split_text(texto):
                doc = (
                    client.table("documentos_rag")
                    .insert(
                        {
                            "chunk_texto": chunk,
                            "id_contrato": contrato["id"],
                            "metadata": metadata,
                            "tokens": len(chunk.split()),
                        }
                    )
                    .execute()
                )
                doc_id = doc.data[0]["id"]
                vetor = model.encode(chunk, normalize_embeddings=True).tolist()
                client.table("embeddings").insert(
                    {
                        "id_documento": doc_id,
                        "vetor": _vetor_para_pgvector(vetor),
                        "modelo": settings.embedding_model,
                    }
                ).execute()
                total_chunks += 1

        log.info("Embeddings gerados: %s chunks", total_chunks)
        return {"status": "ok", "chunks": total_chunks}

    except Exception as exc:
        log.error("Erro ao gerar embeddings: %s", exc)
        raise self.retry(exc=exc, countdown=backoff_countdown(self.request.retries))
