import logging
from typing import Any, AsyncGenerator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from postgrest.exceptions import APIError

from app.core.config import get_settings
from app.core.database import get_supabase_client, rows

log = logging.getLogger("services.rag")

# Função SQL de similaridade (ver scripts/sql/rag_match_function.sql).
MATCH_FUNCTION = "match_documentos"

# Quantos itens incluir no painel agregado que vai junto do contexto semântico.
# A busca top-k não responde perguntas de ranking/contagem ("quem tem mais
# contratos", "obras de maior risco"); o painel injeta esses dados já calculados.
PAINEL_TOP_FORNECEDORES = 10
PAINEL_TOP_OBRAS_RISCO = 8
PAINEL_TOP_FORNECEDORES_VIGENTES = 5

# Situação de contrato que representa "em andamento" no schema (vs. Expirado/Indefinido).
SITUACAO_CONTRATO_VIGENTE = "Vigente"

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


def buscar_documentos(pergunta: str, top_k: int, client: Any | None = None) -> list[dict[str, Any]]:
    """Busca semântica via RPC pgvector (evita o SupabaseVectorStore, incompatível
    com a versão atual do postgrest). Retorna linhas {content, metadata, similarity}."""
    vetor = get_embeddings().embed_query(pergunta)
    client = client or get_supabase_client()
    result = client.rpc(MATCH_FUNCTION, {"query_embedding": vetor, "match_count": top_k}).execute()
    return rows(result)


# ── Painel agregado: contexto estruturado que a busca semântica não cobre ───────
def _detalhe(rotulo: str, valor: Any) -> str | None:
    return f"{rotulo} {valor}" if valor not in (None, "") else None


def _linha_fornecedor(pos: int, f: dict) -> str:
    nome = f.get("razao_social") or f.get("nome") or "(sem nome)"
    cnpj = f" (CNPJ {f['cnpj']})" if f.get("cnpj") else ""
    detalhes = [
        _detalhe("contratos:", f.get("total_contratos")),
        _detalhe("obras em andamento:", f.get("obras_em_andamento")),
        _detalhe("obras concluídas:", f.get("obras_concluidas")),
        _detalhe("valor total R$", f.get("valor_total")),
        _detalhe("taxa de aditivo:", f.get("taxa_aditivo")),
        _detalhe("prob. média de atraso:", f.get("media_prob_atraso")),
    ]
    return f"{pos}. {nome}{cnpj} — " + "; ".join(d for d in detalhes if d)


def _painel_fornecedores(client: Any) -> list[str]:
    linhas = rows(
        client.table("mv_fornecedores_ranking")
        .select("*")
        .order("total_contratos", desc=True)
        .limit(PAINEL_TOP_FORNECEDORES)
        .execute()
    )
    if not linhas:
        return []
    cabecalho = f"Fornecedores com mais contratos (top {len(linhas)}):"
    return [cabecalho] + [_linha_fornecedor(i, f) for i, f in enumerate(linhas, 1)]


def _nomes_fornecedores(client: Any, ids: list[str]) -> dict[str, str]:
    """Resolve `id_fornecedor -> razão social` para os ids informados."""
    if not ids:
        return {}
    linhas = rows(client.table("fornecedores").select("*").in_("id", ids).execute())
    return {
        f["id"]: (f.get("razao_social") or f.get("nome") or "(sem nome)")
        for f in linhas
        if f.get("id")
    }


def _painel_contratos(client: Any) -> list[str]:
    """Totais de contratos por situação + ranking de fornecedores com mais contratos
    vigentes (em andamento) — responde perguntas que dependem da situação do contrato,
    dimensão ausente do ranking pré-agregado de fornecedores."""
    contratos = rows(client.table("contratos").select("id_fornecedor,situacao").execute())
    if not contratos:
        return []

    por_situacao: dict[str, int] = {}
    vigentes_por_forn: dict[str, int] = {}
    for ct in contratos:
        situacao = ct.get("situacao") or "não informada"
        por_situacao[situacao] = por_situacao.get(situacao, 0) + 1
        if situacao == SITUACAO_CONTRATO_VIGENTE and ct.get("id_fornecedor"):
            fid = ct["id_fornecedor"]
            vigentes_por_forn[fid] = vigentes_por_forn.get(fid, 0) + 1

    blocos = [
        f"Total de contratos cadastrados: {len(contratos)}.",
        "Contratos por situação: "
        + "; ".join(f"{s}: {n}" for s, n in sorted(por_situacao.items())),
    ]

    if vigentes_por_forn:
        top = sorted(vigentes_por_forn.items(), key=lambda kv: kv[1], reverse=True)[
            :PAINEL_TOP_FORNECEDORES_VIGENTES
        ]
        nomes = _nomes_fornecedores(client, [fid for fid, _ in top])
        blocos.append(f"Fornecedores com mais contratos vigentes/em andamento (top {len(top)}):")
        blocos += [
            f"{i}. {nomes.get(fid, '(sem nome)')} — {qtd} contratos vigentes"
            for i, (fid, qtd) in enumerate(top, 1)
        ]
    return blocos


def _painel_obras(client: Any) -> list[str]:
    linhas = rows(
        client.table("mv_obras_resumo")
        .select("nome,secretaria,situacao,nivel_risco,prob_atraso")
        .execute()
    )
    if not linhas:
        return []

    blocos = [f"Total de obras cadastradas: {len(linhas)}."]

    contagem: dict[str, int] = {}
    for o in linhas:
        situacao = o.get("situacao") or "não informada"
        contagem[situacao] = contagem.get(situacao, 0) + 1
    blocos.append(
        "Obras por situação: " + "; ".join(f"{s}: {n}" for s, n in sorted(contagem.items()))
    )

    com_risco = sorted(
        (o for o in linhas if o.get("prob_atraso") is not None),
        key=lambda o: o["prob_atraso"],
        reverse=True,
    )[:PAINEL_TOP_OBRAS_RISCO]
    if com_risco:
        blocos.append(f"Obras com maior probabilidade de atraso (top {len(com_risco)}):")
        blocos += [
            f"{i}. {o.get('nome', '(sem nome)')} — prob. atraso {o['prob_atraso']}; "
            f"risco {o.get('nivel_risco', '?')}; secretaria {o.get('secretaria', '?')}"
            for i, o in enumerate(com_risco, 1)
        ]
    return blocos


def carregar_painel(client: Any) -> str:
    """Monta o painel de dados agregados (rankings e totais já calculados) para dar
    ao LLM o contexto que a busca top-k não cobre. Cada bloco degrada de forma
    independente: se uma view materializada estiver stale/indisponível, segue sem
    ela em vez de derrubar a consulta inteira."""
    blocos: list[str] = []
    for montar in (_painel_fornecedores, _painel_contratos, _painel_obras):
        try:
            blocos += montar(client)
        except APIError as exc:
            log.warning("Painel agregado indisponível (%s): %s", montar.__name__, exc)
    return "\n".join(blocos)


def montar_contexto(pergunta: str, top_k: int) -> str:
    """Contexto do RAG = painel agregado (rankings/totais) + trechos semânticos
    relevantes à pergunta. O painel responde perguntas analíticas; os trechos,
    perguntas sobre contratos/obras específicos."""
    client = get_supabase_client()
    secoes: list[str] = []

    painel = carregar_painel(client)
    if painel:
        secoes.append(
            "PAINEL DE DADOS AGREGADOS DO MUNICÍPIO (rankings e totais já calculados):\n" + painel
        )

    semantico = _formatar_contexto(buscar_documentos(pergunta, top_k, client))
    if semantico:
        secoes.append("TRECHOS DE CONTRATOS E OBRAS RELACIONADOS À PERGUNTA:\n" + semantico)

    return "\n\n===\n\n".join(secoes)


# ── Prompt em português contextualizado para obras de Macaé ────────────────────
PROMPT = ChatPromptTemplate.from_template(
    """Você é um assistente especializado em análise de obras públicas e contratos \
do município de Macaé, Rio de Janeiro. Você ajuda gestores a entender obras, \
contratos, fornecedores, prazos e riscos.

O CONTEXTO abaixo tem duas partes:
1. PAINEL DE DADOS AGREGADOS — rankings e totais já calculados de todo o município \
(ex.: fornecedores com mais contratos, total de obras, obras por situação, obras \
de maior risco). Use-o para perguntas de contagem, ranking, comparação ou visão \
geral ("quais", "quantos", "o maior", "o que você sabe").
2. TRECHOS DE CONTRATOS E OBRAS — detalhes específicos recuperados para a pergunta.

Responda com base EXCLUSIVAMENTE no contexto fornecido. Se a pergunta for sobre \
o que você conhece ou sobre a base de dados, descreva os dados de obras, contratos \
e fornecedores de Macaé disponíveis no contexto. Se a informação realmente não \
estiver no contexto, diga claramente que não encontrou dados suficientes. Nunca \
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
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


async def consultar(pergunta: str) -> dict:
    """Executa consulta RAG e retorna a resposta completa."""
    try:
        top_k = get_settings().rag_top_k
        contexto = montar_contexto(pergunta, top_k)
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
        contexto = montar_contexto(pergunta, top_k)
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
