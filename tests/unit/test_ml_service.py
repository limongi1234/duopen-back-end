import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.core.config.get_settings") as mock:
        s = MagicMock()
        s.secret_key = "test-secret-key-for-testing-minimum-32"
        s.algorithm = "HS256"
        s.access_token_expire = 15
        s.refresh_token_expire = 10080
        s.openai_api_key = "sk-test"
        s.embedding_model = "text-embedding-3-small"
        mock.return_value = s
        yield s


def test_ml_service_get_predicao_found():
    from app.services.ml_service import MLService

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "p1", "id_obra": "obra-123", "prob_atraso": 0.5, "nivel_risco": "medio"}
    ]
    service = MLService(db)
    result = service.get_predicao("obra-123")

    assert result["id_obra"] == "obra-123"
    db.table.assert_called_with("predicoes")


def test_ml_service_get_predicao_not_found():
    from app.services.ml_service import MLService

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    service = MLService(db)

    assert service.get_predicao("inexistente") is None


def test_ml_service_listar_predicoes():
    from app.services.ml_service import MLService

    db = MagicMock()
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"id_obra": "o1"},
        {"id_obra": "o2"},
    ]
    service = MLService(db)
    result = service.listar_predicoes()

    assert len(result) == 2


def test_ml_service_listar_predicoes_filtra_nivel_risco():
    from app.services.ml_service import MLService

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id_obra": "o1", "nivel_risco": "alto"}
    ]
    service = MLService(db)
    result = service.listar_predicoes(nivel_risco="alto")

    assert len(result) == 1
    db.table.return_value.select.return_value.eq.assert_called_with("nivel_risco", "alto")


@pytest.mark.asyncio
async def test_rag_service_query():
    from app.services.rag_service import RAGService

    service = RAGService()
    result = await service.query("Qual a eficiência?", obra_id="obra-1", top_k=3)

    assert isinstance(result.resposta, str)
    assert isinstance(result.fontes, list)


@pytest.mark.asyncio
async def test_rag_service_query_no_obra():
    from app.services.rag_service import RAGService

    service = RAGService()
    result = await service.query("Pergunta geral?")

    assert result.resposta is not None
