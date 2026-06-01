from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.services.rag_service as rag


@pytest.fixture(autouse=True)
def reset_singletons():
    rag._embeddings = None
    rag._llm = None
    yield
    rag._embeddings = None
    rag._llm = None


def test_get_embeddings_retorna_singleton():
    with patch("app.services.rag_service.HuggingFaceEmbeddings") as mock_hf:
        mock_hf.return_value = MagicMock()
        a = rag.get_embeddings()
        b = rag.get_embeddings()

    assert a is b
    mock_hf.assert_called_once()


def test_get_embeddings_dimensao_384():
    with patch("app.services.rag_service.HuggingFaceEmbeddings") as mock_hf:
        inst = MagicMock()
        inst.embed_query.return_value = [0.0] * 384
        mock_hf.return_value = inst
        emb = rag.get_embeddings()

    assert mock_hf.call_args.kwargs["model_name"] == "paraphrase-multilingual-MiniLM-L12-v2"
    assert len(emb.embed_query("teste")) == 384


def test_formatar_contexto_separa_com_separador():
    docs = [{"content": "A"}, {"content": "B"}]
    assert rag._formatar_contexto(docs) == "A\n\n---\n\nB"


def test_buscar_documentos_chama_rpc():
    fake_emb = MagicMock()
    fake_emb.embed_query.return_value = [0.1] * 384
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = [
        {"content": "trecho", "metadata": {"id_contrato": "c1"}, "similarity": 0.9}
    ]
    with patch("app.services.rag_service.get_embeddings", return_value=fake_emb), \
         patch("app.services.rag_service.get_supabase_client", return_value=client):
        docs = rag.buscar_documentos("pergunta?", 5)

    assert docs[0]["content"] == "trecho"
    client.rpc.assert_called_with(
        "match_documentos", {"query_embedding": [0.1] * 384, "match_count": 5}
    )


@pytest.mark.asyncio
async def test_consultar_retorna_resposta():
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda

    from app.core.config import get_settings

    fake_llm = RunnableLambda(lambda msgs: AIMessage(content="Resposta da IA"))
    with patch("app.services.rag_service.buscar_documentos",
               return_value=[{"content": "ctx", "metadata": {}}]), \
         patch("app.services.rag_service.get_llm", return_value=fake_llm):
        out = await rag.consultar("pergunta?")

    assert out["resposta"] == "Resposta da IA"
    assert out["modelo"] == get_settings().llm_model


@pytest.mark.asyncio
async def test_consultar_trata_excecao_sem_quebrar():
    with patch("app.services.rag_service.buscar_documentos", side_effect=RuntimeError("boom")):
        out = await rag.consultar("x")

    assert out["modelo"] is None
    assert "Não foi possível" in out["resposta"]


@pytest.mark.asyncio
async def test_consultar_stream_emite_tokens():
    async def fake_astream(msgs):
        for token in ["Olá", " mundo"]:
            yield SimpleNamespace(content=token)

    fake_llm = MagicMock()
    fake_llm.astream = fake_astream

    with patch("app.services.rag_service.buscar_documentos", return_value=[{"content": "ctx"}]), \
         patch("app.services.rag_service.get_llm", return_value=fake_llm):
        chunks = [c async for c in rag.consultar_stream("pergunta?")]

    assert "data: Olá\n\n" in chunks
    assert "data:  mundo\n\n" in chunks


@pytest.mark.asyncio
async def test_consultar_stream_finaliza_com_done():
    async def fake_astream(msgs):
        yield SimpleNamespace(content="ok")

    fake_llm = MagicMock()
    fake_llm.astream = fake_astream

    with patch("app.services.rag_service.buscar_documentos", return_value=[]), \
         patch("app.services.rag_service.get_llm", return_value=fake_llm):
        chunks = [c async for c in rag.consultar_stream("pergunta?")]

    assert chunks[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_consultar_stream_trata_erro():
    with patch("app.services.rag_service.buscar_documentos", side_effect=RuntimeError("boom")):
        chunks = [c async for c in rag.consultar_stream("x")]

    assert any("Erro ao processar" in c for c in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"
