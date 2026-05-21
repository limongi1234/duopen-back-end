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


@pytest.mark.asyncio
async def test_ml_service_predict():
    from app.services.ml_service import MLService

    service = MLService()
    result = await service.predict("obra-123")

    assert result.obra_id == "obra-123"
    assert result.risco_atraso == 0.0
    assert result.risco_sobrecusto == 0.0
    assert result.score_eficiencia == 0.0
    assert result.recomendacoes == []


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
