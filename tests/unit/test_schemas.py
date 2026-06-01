from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest
from app.schemas.ml import MLAnalysisRequest, RAGQuery
from app.schemas.obras import ObraCreate, ObraUpdate


def test_obra_create_valid():
    obra = ObraCreate(
        nome="Obra Teste",
        valor_contrato=100000.0,
        data_inicio=date(2026, 1, 1),
        data_prevista_fim=date(2026, 12, 31),
    )
    assert obra.nome == "Obra Teste"
    assert obra.municipio == "Macaé"


def test_obra_update_partial():
    update = ObraUpdate(status="concluida")
    assert update.status == "concluida"
    assert update.nome is None


def test_login_request_valid():
    req = LoginRequest(email="user@example.com", password="senha123")
    assert req.email == "user@example.com"


def test_login_request_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(email="nao-e-email", password="senha123")


def test_rag_query_defaults():
    q = RAGQuery(pergunta="Qual a eficiência da obra?")
    assert q.top_k == 5
    assert q.obra_id is None


def test_ml_analysis_request():
    req = MLAnalysisRequest(obra_id="abc-123")
    assert req.obra_id == "abc-123"
