import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


def make_settings():
    s = MagicMock()
    s.supabase_url = "https://test.supabase.co"
    s.supabase_key = "test-key"
    s.secret_key = "test-secret-key-for-testing-minimum-32"
    s.algorithm = "HS256"
    s.access_token_expire = 15
    s.refresh_token_expire = 10080
    s.redis_url = "redis://localhost:6379/0"
    s.openai_api_key = "sk-test"
    s.embedding_model = "text-embedding-3-small"
    s.log_level = "INFO"
    s.environment = "test"
    s.cors_origins = ["http://localhost:5173"]
    return s


def test_health_ok():
    with patch("app.core.config.get_settings", return_value=make_settings()), \
         patch("app.main.check_connection", new=AsyncMock(return_value=True)):
        from app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_degraded():
    with patch("app.core.config.get_settings", return_value=make_settings()), \
         patch("app.main.check_connection", new=AsyncMock(return_value=False)):
        from app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "error"
