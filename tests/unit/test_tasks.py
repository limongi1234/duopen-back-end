from unittest.mock import MagicMock

import pytest


def test_backoff_countdown_exponencial():
    from app.tasks.celery_app import RETRY_BACKOFF_MAX, backoff_countdown

    # 2, 4, 8, 16, ... (base 2, dobrando a cada tentativa)
    assert backoff_countdown(0) == 2
    assert backoff_countdown(1) == 4
    assert backoff_countdown(2) == 8
    assert backoff_countdown(3) == 16
    # respeita o teto máximo
    assert backoff_countdown(100) == RETRY_BACKOFF_MAX


def test_run_ml_analysis_success():
    from app.tasks.ml_tasks import run_ml_analysis

    # Celery com bind=True injeta self automaticamente; chamar sem mock_self
    result = run_ml_analysis("obra-123")

    assert result == {"obra_id": "obra-123", "status": "completed"}


def test_run_ml_retraining_success():
    from app.tasks.ml_tasks import run_ml_retraining

    result = run_ml_retraining()

    assert result == {"status": "completed"}


def test_run_ml_analysis_retries_on_error():
    import app.tasks.ml_tasks as ml_module
    from app.tasks.ml_tasks import run_ml_analysis

    mock_log = MagicMock()
    mock_log.info.side_effect = RuntimeError("forced error")
    original_log = ml_module.log
    ml_module.log = mock_log

    try:
        run_ml_analysis("obra-123")
    except Exception:
        pass  # Celery levanta Retry quando não há worker
    finally:
        ml_module.log = original_log

    mock_log.error.assert_called_once()


def test_e_rate_limit_reconhece_429():
    import app.tasks.embedding_tasks as emb

    assert emb._e_rate_limit(Exception("429 RESOURCE_EXHAUSTED ... limit: 100"))
    assert emb._e_rate_limit(Exception("RESOURCE_EXHAUSTED"))
    assert not emb._e_rate_limit(Exception("400 INVALID_ARGUMENT"))


def test_espera_sugerida_extrai_da_mensagem():
    import app.tasks.embedding_tasks as emb

    # usa o atraso sugerido pela API quando presente (+1s de margem)
    assert emb._espera_sugerida(Exception("Please retry in 26.27s.")) == pytest.approx(27.27)
    # cai no padrão quando a mensagem não traz o atraso
    assert emb._espera_sugerida(Exception("sem dica")) == emb.RATE_LIMIT_ESPERA_PADRAO_S


def test_embed_chunks_recua_no_rate_limit_e_retoma():
    from unittest.mock import patch

    import app.tasks.embedding_tasks as emb

    erro = Exception("429 RESOURCE_EXHAUSTED. Please retry in 5s.")
    # falha 1x por rate limit, depois passa
    fake = MagicMock(side_effect=[erro, [[0.1] * 384]])
    sleeps = []
    with (
        patch("app.tasks.embedding_tasks.embed_documentos", fake),
        patch("app.tasks.embedding_tasks.time.sleep", side_effect=sleeps.append),
    ):
        out = emb._embed_chunks(["chunk"])

    assert out == [[0.1] * 384]
    assert fake.call_count == 2  # tentou de novo após o recuo
    assert sleeps == [pytest.approx(6.0)]  # aguardou ~5s sugeridos + margem


def test_embed_chunks_propaga_erro_nao_rate_limit():
    from unittest.mock import patch

    import app.tasks.embedding_tasks as emb

    with patch("app.tasks.embedding_tasks.embed_documentos", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            emb._embed_chunks(["chunk"])


def test_task_gerar_embeddings_enriquece_com_obra():
    from unittest.mock import patch

    import app.tasks.embedding_tasks as emb

    client = MagicMock()
    docs_tbl = MagicMock()
    docs_tbl.select.return_value.execute.return_value.data = []  # nada indexado ainda
    docs_tbl.insert.return_value.execute.return_value.data = [{"id": "doc1"}]
    contratos_tbl = MagicMock()
    contratos_tbl.select.return_value.execute.return_value.data = [
        {
            "id": "c1",
            "id_obra": "o1",
            "id_fornecedor": "f1",
            "numero": "001/2026",
            "objeto": "Pavimentação",
            "modalidade": "Pregão",
            "situacao": "Em andamento",
            "valor_global": 100.0,
            "valor_final": 90.0,
        }
    ]
    mv_tbl = MagicMock()
    mv_tbl.select.return_value.execute.return_value.data = [
        {
            "id": "o1",
            "nome": "Escola Municipal",
            "secretaria": "Educação",
            "bairro": "Centro",
            "nivel_risco": "alto",
            "prob_atraso": 0.9,
            "situacao": "Em andamento",
        }
    ]
    forn_tbl = MagicMock()
    forn_tbl.select.return_value.execute.return_value.data = [
        {"id": "f1", "razao_social": "Construtora Alfa LTDA", "cnpj": "12.345.678/0001-90"}
    ]
    emb_tbl = MagicMock()
    client.table.side_effect = lambda name: {
        "documentos_rag": docs_tbl,
        "contratos": contratos_tbl,
        "mv_obras_resumo": mv_tbl,
        "fornecedores": forn_tbl,
        "embeddings": emb_tbl,
    }[name]

    captured = {}

    def fake_split(texto):
        captured["texto"] = texto
        return ["chunk1"]

    splitter = MagicMock()
    splitter.split_text.side_effect = fake_split

    with (
        patch("app.tasks.embedding_tasks.get_supabase_client", return_value=client),
        patch("app.tasks.embedding_tasks.release_lock") as mock_release,
        patch("app.tasks.embedding_tasks.embed_documentos", return_value=[[0.1] * 384]),
        patch("langchain_text_splitters.RecursiveCharacterTextSplitter", return_value=splitter),
    ):
        result = emb.task_gerar_embeddings()

    assert result == {"status": "ok", "chunks": 1}
    emb_tbl.insert.assert_called_once()
    # texto indexado enriquecido com contexto da obra e do fornecedor
    assert "Escola Municipal" in captured["texto"]
    assert "Educação" in captured["texto"]
    assert "alto" in captured["texto"]
    assert "Construtora Alfa LTDA" in captured["texto"]
    assert "12.345.678/0001-90" in captured["texto"]
    # metadata enriquecida
    meta = docs_tbl.insert.call_args[0][0]["metadata"]
    assert meta["id_obra"] == "o1"
    assert meta["secretaria"] == "Educação"
    assert meta["nivel_risco"] == "alto"
    assert meta["obra"] == "Escola Municipal"
    assert meta["fornecedor"] == "Construtora Alfa LTDA"
    assert meta["cnpj_fornecedor"] == "12.345.678/0001-90"
    assert meta["numero_contrato"] == "001/2026"
    mock_release.assert_called_once()  # sucesso libera o lock


def test_task_gerar_embeddings_forcar_recria_indice():
    from unittest.mock import patch

    import app.tasks.embedding_tasks as emb

    client = MagicMock()
    docs_tbl = MagicMock()
    # contrato c1 JÁ indexado — no modo incremental seria pulado; forçando, reprocessa.
    docs_tbl.select.return_value.execute.return_value.data = [{"id_contrato": "c1"}]
    docs_tbl.insert.return_value.execute.return_value.data = [{"id": "doc1"}]
    contratos_tbl = MagicMock()
    contratos_tbl.select.return_value.execute.return_value.data = [
        {
            "id": "c1",
            "id_obra": "o1",
            "id_fornecedor": "f1",
            "numero": "001/2026",
            "objeto": "X",
            "modalidade": "Pregão",
            "situacao": "Em andamento",
            "valor_global": 100.0,
            "valor_final": 90.0,
        }
    ]
    mv_tbl = MagicMock()
    mv_tbl.select.return_value.execute.return_value.data = []
    forn_tbl = MagicMock()
    forn_tbl.select.return_value.execute.return_value.data = []
    emb_tbl = MagicMock()
    client.table.side_effect = lambda name: {
        "documentos_rag": docs_tbl,
        "contratos": contratos_tbl,
        "mv_obras_resumo": mv_tbl,
        "fornecedores": forn_tbl,
        "embeddings": emb_tbl,
    }[name]

    splitter = MagicMock()
    splitter.split_text.return_value = ["chunk1"]

    with (
        patch("app.tasks.embedding_tasks.get_supabase_client", return_value=client),
        patch("app.tasks.embedding_tasks.release_lock") as mock_release,
        patch("app.tasks.embedding_tasks.embed_documentos", return_value=[[0.1] * 384]),
        patch("langchain_text_splitters.RecursiveCharacterTextSplitter", return_value=splitter),
    ):
        result = emb.task_gerar_embeddings(forcar=True)

    # apagou o índice antes de regerar (embeddings e documentos_rag)
    emb_tbl.delete.assert_called()
    docs_tbl.delete.assert_called()
    # reprocessou mesmo o contrato já indexado
    assert result == {"status": "ok", "chunks": 1}
    mock_release.assert_called_once()  # sucesso libera o lock


def test_task_gerar_embeddings_retries_on_error():
    from unittest.mock import patch

    import app.tasks.embedding_tasks as emb

    mock_log = MagicMock()
    original_log = emb.log
    emb.log = mock_log
    # get_supabase_client é chamado antes de instanciar o modelo → sem download.
    try:
        with (
            patch(
                "app.tasks.embedding_tasks.get_supabase_client",
                side_effect=RuntimeError("forced error"),
            ),
            patch("app.tasks.embedding_tasks.release_lock") as mock_release,
        ):
            emb.task_gerar_embeddings()
    except Exception:
        pass
    finally:
        emb.log = original_log

    mock_log.error.assert_called_once()
    # erro transitório (retry) NÃO deve liberar o lock — só ao esgotar os retries
    mock_release.assert_not_called()
