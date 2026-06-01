from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_supabase():
    with patch("app.core.database.get_supabase_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def client(mock_supabase):
    with patch("app.core.config.get_settings") as mock_settings:
        settings = MagicMock()
        settings.supabase_url = "https://test.supabase.co"
        settings.supabase_key = "test-key"
        settings.secret_key = "test-secret-key-for-testing-only-32ch"
        settings.algorithm = "HS256"
        settings.access_token_expire = 15
        settings.refresh_token_expire = 10080
        settings.redis_url = "redis://localhost:6379/0"
        settings.openai_api_key = "sk-test"
        settings.embedding_model = "text-embedding-3-small"
        settings.log_level = "INFO"
        settings.environment = "test"
        settings.cors_origins = ["http://localhost:5173"]
        mock_settings.return_value = settings

        from app.main import app
        with TestClient(app) as c:
            yield c
