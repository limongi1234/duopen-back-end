import pytest
from unittest.mock import patch, MagicMock


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
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.services.rag_service import RAGService

    chain = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value={
                "result": "Resposta baseada nos contratos.",
                "source_documents": [
                    SimpleNamespace(
                        page_content="trecho do contrato",
                        metadata={"id_contrato": "c1"},
                    )
                ],
            }
        )
    )
    with patch("app.services.rag_service.RetrievalQA") as mock_qa, \
         patch("app.services.rag_service.SupabaseVectorStore"), \
         patch("app.services.rag_service.OpenAIEmbeddings"), \
         patch("app.services.rag_service.ChatOpenAI"), \
         patch("app.services.rag_service.get_supabase_client"):
        mock_qa.from_chain_type.return_value = chain
        result = await RAGService().query("Qual a eficiência?", obra_id="obra-1", top_k=3)

    assert result.resposta == "Resposta baseada nos contratos."
    assert result.fontes[0]["conteudo"] == "trecho do contrato"
    assert result.fontes[0]["metadata"]["id_contrato"] == "c1"


@pytest.mark.asyncio
async def test_rag_service_stream():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from app.services.rag_service import RAGService

    retriever = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value=[SimpleNamespace(page_content="contexto", metadata={})]
        )
    )

    async def fake_astream(prompt):
        for token in ["Res", "posta"]:
            yield SimpleNamespace(content=token)

    llm = MagicMock()
    llm.astream = fake_astream

    with patch("app.services.rag_service.SupabaseVectorStore") as mock_vs, \
         patch("app.services.rag_service.OpenAIEmbeddings"), \
         patch("app.services.rag_service.ChatOpenAI", return_value=llm), \
         patch("app.services.rag_service.get_supabase_client"):
        mock_vs.return_value.as_retriever.return_value = retriever
        tokens = [token async for token in RAGService().stream("pergunta?")]

    assert tokens == ["Res", "posta"]
