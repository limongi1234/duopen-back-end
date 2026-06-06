import logging
import re
import time
from typing import Any, Optional

from celery.exceptions import MaxRetriesExceededError
from postgrest.exceptions import APIError

from app.core.config import get_settings
from app.core.database import first, get_supabase_client, rows
from app.core.locks import release_lock
from app.services.embeddings import embed_documentos
from app.tasks.celery_app import backoff_countdown, celery_app

log = logging.getLogger("tasks.embedding")

CHUNK_SIZE = 512  # caracteres por chunk
CHUNK_OVERLAP = 50  # sobreposição entre chunks
_UUID_ZERO = "00000000-0000-0000-0000-000000000000"  # filtro "match-all" para delete

# Embeddings via API têm cota grátis de 100 req/min. Em vez de quebrar o re-index,
# recuamos no 429 e retomamos — respeitando o atraso sugerido pela própria API.
RATE_LIMIT_ESPERA_PADRAO_S = 30.0
EMBED_MAX_TENTATIVAS = 6
_RE_RETRY = re.compile(r"retry in ([0-9.]+)s")


def _e_rate_limit(exc: Exception) -> bool:
    txt = str(exc)
    return "429" in txt or "RESOURCE_EXHAUSTED" in txt


def _espera_sugerida(exc: Exception) -> float:
    """Atraso sugerido pela API (+1s de margem); cai no padrão se não houver dica."""
    m = _RE_RETRY.search(str(exc))
    return float(m.group(1)) + 1 if m else RATE_LIMIT_ESPERA_PADRAO_S


def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embeda uma leva de chunks com recuo em caso de rate limit (cota grátis)."""
    for tentativa in range(EMBED_MAX_TENTATIVAS):
        try:
            return embed_documentos(chunks)
        except Exception as exc:
            if not _e_rate_limit(exc) or tentativa == EMBED_MAX_TENTATIVAS - 1:
                raise
            espera = _espera_sugerida(exc)
            log.warning(
                "Rate limit do Gemini; aguardando %.0fs (tentativa %d/%d)",
                espera,
                tentativa + 1,
                EMBED_MAX_TENTATIVAS,
            )
            time.sleep(espera)
    raise RuntimeError("inalcançável")  # pragma: no cover


# Lock distribuído que serializa a indexação (adquirido no endpoint, liberado aqui).
EMBEDDINGS_LOCK_KEY = "duopen:lock:embeddings"
EMBEDDINGS_LOCK_TTL = 1800  # 30 min — rede de segurança caso o worker morra


def _linha(rotulo: str, valor: Any) -> Optional[str]:
    return f"{rotulo}: {valor}" if valor not in (None, "") else None


def _nome_fornecedor(fornecedor: Optional[dict]) -> Optional[str]:
    fornecedor = fornecedor or {}
    return fornecedor.get("razao_social") or fornecedor.get("nome")


def _montar_texto(contrato: dict, obra: Optional[dict], fornecedor: Optional[dict] = None) -> str:
    """Texto indexável do contrato, enriquecido com o fornecedor e o contexto da
    obra vinculada — para que a busca semântica responda também sobre quem executa."""
    linhas = [
        _linha("Número do contrato", contrato.get("numero")),
        _linha("Fornecedor", _nome_fornecedor(fornecedor)),
        _linha("CNPJ do fornecedor", (fornecedor or {}).get("cnpj")),
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


def _metadata(contrato: dict, obra: Optional[dict], fornecedor: Optional[dict] = None) -> dict:
    obra = obra or {}
    return {
        "id_contrato": contrato["id"],
        "id_obra": contrato.get("id_obra"),
        "numero_contrato": contrato.get("numero"),
        "modalidade": contrato.get("modalidade"),
        "situacao_contrato": contrato.get("situacao"),
        "fornecedor": _nome_fornecedor(fornecedor),
        "cnpj_fornecedor": (fornecedor or {}).get("cnpj"),
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
        linhas = rows(
            client.table("mv_obras_resumo")
            .select("id,nome,secretaria,bairro,nivel_risco,prob_atraso,situacao")
            .execute()
        )
        return {o["id"]: o for o in linhas}
    except APIError as exc:
        log.warning("Enriquecimento indisponível (mv_obras_resumo): %s", exc)
        return {}


def _carregar_fornecedores(client) -> dict[str, dict]:
    """Lookup `id_fornecedor -> {razao_social/nome, cnpj}` para enriquecer cada
    contrato com quem o executa. Degrada com elegância se a tabela estiver indisponível."""
    try:
        linhas = rows(client.table("fornecedores").select("*").execute())
        return {f["id"]: f for f in linhas if f.get("id")}
    except APIError as exc:
        log.warning("Enriquecimento indisponível (fornecedores): %s", exc)
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

    Modelo: gemini-embedding-001 via API (384 dims, output_dimensionality).
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        settings = get_settings()
        client = get_supabase_client()
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
                for r in rows(client.table("documentos_rag").select("id_contrato").execute())
                if r.get("id_contrato")
            }
        contratos = rows(
            client.table("contratos")
            .select(
                "id,id_obra,id_fornecedor,numero,objeto,modalidade,"
                "situacao,valor_global,valor_final"
            )
            .execute()
        )
        obras_por_id = _carregar_obras(client)
        fornecedores_por_id = _carregar_fornecedores(client)

        total_chunks = 0
        for contrato in contratos:
            if contrato["id"] in ja_indexados:
                continue
            obra = obras_por_id.get(contrato.get("id_obra") or "")
            fornecedor = fornecedores_por_id.get(contrato.get("id_fornecedor") or "")
            texto = _montar_texto(contrato, obra, fornecedor)
            if not texto.strip():
                continue

            metadata = _metadata(contrato, obra, fornecedor)
            chunks = splitter.split_text(texto)
            if not chunks:
                continue
            # Embeda todos os chunks do contrato numa só chamada à API (menos
            # requisições -> menor risco de rate limit), com recuo no 429.
            vetores = _embed_chunks(chunks)
            for chunk, vetor in zip(chunks, vetores, strict=True):
                doc = first(
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
                if doc is None:
                    continue
                client.table("embeddings").insert(
                    {
                        "id_documento": doc["id"],
                        "vetor": _vetor_para_pgvector(vetor),
                        "modelo": settings.embedding_model,
                    }
                ).execute()
                total_chunks += 1

        log.info("Embeddings gerados: %s chunks", total_chunks)
        release_lock(EMBEDDINGS_LOCK_KEY)  # sucesso -> libera o lock
        return {"status": "ok", "chunks": total_chunks}

    except Exception as exc:
        log.error("Erro ao gerar embeddings: %s", exc)
        # Mantém o lock entre tentativas; só libera ao esgotar os retries.
        try:
            raise self.retry(exc=exc, countdown=backoff_countdown(self.request.retries))
        except MaxRetriesExceededError:
            release_lock(EMBEDDINGS_LOCK_KEY)
            raise
