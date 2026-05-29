import logging

from app.tasks.celery_app import celery_app, backoff_countdown
from app.core.config import get_settings
from app.core.database import get_supabase_client

log = logging.getLogger("tasks.embedding")

CHUNK_SIZE = 512   # caracteres por chunk
CHUNK_OVERLAP = 50  # sobreposição entre chunks


def _montar_texto(contrato: dict) -> str:
    """Monta o texto indexável de um contrato a partir dos campos disponíveis."""
    partes = [
        f"Objeto: {contrato.get('objeto')}" if contrato.get("objeto") else "",
        f"Modalidade: {contrato.get('modalidade')}" if contrato.get("modalidade") else "",
        f"Situação: {contrato.get('situacao')}" if contrato.get("situacao") else "",
        f"Valor global: R$ {contrato.get('valor_global')}" if contrato.get("valor_global") else "",
        f"Valor final: R$ {contrato.get('valor_final')}" if contrato.get("valor_final") else "",
    ]
    return "\n".join(p for p in partes if p)


def _vetor_para_pgvector(vetor: list[float]) -> str:
    """pgvector aceita o literal textual '[v1,v2,...]'."""
    return "[" + ",".join(str(v) for v in vetor) + "]"


@celery_app.task(bind=True, max_retries=3)
def task_gerar_embeddings(self) -> dict:
    """Indexa em `documentos_rag`/`embeddings` os contratos ainda sem embedding.

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

        ja_indexados = {
            r["id_contrato"]
            for r in (client.table("documentos_rag").select("id_contrato").execute().data or [])
            if r.get("id_contrato")
        }
        contratos = (
            client.table("contratos")
            .select("id,objeto,modalidade,situacao,valor_global,valor_final")
            .execute()
            .data
            or []
        )

        total_chunks = 0
        for contrato in contratos:
            if contrato["id"] in ja_indexados:
                continue
            texto = _montar_texto(contrato)
            if not texto.strip():
                continue

            for chunk in splitter.split_text(texto):
                doc = (
                    client.table("documentos_rag")
                    .insert(
                        {
                            "chunk_texto": chunk,
                            "id_contrato": contrato["id"],
                            "metadata": {
                                "modalidade": contrato.get("modalidade"),
                                "situacao": contrato.get("situacao"),
                            },
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
