import math
from unittest.mock import MagicMock, patch

import pytest

import app.services.embeddings as emb


@pytest.fixture(autouse=True)
def reset_cache():
    emb.reset_cache()
    yield
    emb.reset_cache()


def test_provider_singleton_por_task_type():
    with patch("app.services.embeddings.GoogleGenerativeAIEmbeddings") as mock_g:
        mock_g.side_effect = lambda **kw: MagicMock()
        q1 = emb._provider(emb.TASK_QUERY)
        q2 = emb._provider(emb.TASK_QUERY)
        d1 = emb._provider(emb.TASK_DOCUMENT)

    assert q1 is q2  # mesmo task_type reaproveita a instância
    assert d1 is not q1  # task_type diferente -> instância própria
    kwargs = mock_g.call_args_list[0].kwargs
    assert kwargs["output_dimensionality"] == emb.EMBEDDING_DIMS == 384
    assert kwargs["task_type"] == emb.TASK_QUERY


def test_normalizar_gera_vetor_unitario():
    out = emb._normalizar([3.0, 4.0])
    assert out == [0.6, 0.8]
    assert math.isclose(math.sqrt(sum(v * v for v in out)), 1.0)


def test_normalizar_vetor_zero_nao_quebra():
    assert emb._normalizar([0.0, 0.0]) == [0.0, 0.0]


def test_embed_pergunta_usa_task_query_e_normaliza():
    fake = MagicMock()
    fake.embed_query.return_value = [3.0, 4.0]  # não-unitário (como o Gemini truncado)
    with patch("app.services.embeddings._provider", return_value=fake) as mock_p:
        out = emb.embed_pergunta("quanto custa a obra?")

    mock_p.assert_called_once_with(emb.TASK_QUERY)
    fake.embed_query.assert_called_once_with("quanto custa a obra?")
    assert math.isclose(math.sqrt(sum(v * v for v in out)), 1.0)


def test_embed_documentos_em_lote_usa_task_document_e_normaliza():
    fake = MagicMock()
    fake.embed_documents.return_value = [[3.0, 4.0], [0.0, 5.0]]
    with patch("app.services.embeddings._provider", return_value=fake) as mock_p:
        out = emb.embed_documentos(["a", "b"])

    mock_p.assert_called_once_with(emb.TASK_DOCUMENT)
    fake.embed_documents.assert_called_once_with(["a", "b"])
    assert len(out) == 2
    for v in out:
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0)
