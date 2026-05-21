import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "test-secret-key-for-testing-minimum-32"
ALGORITHM = "HS256"


def make_settings():
    s = MagicMock()
    s.supabase_url = "https://test.supabase.co"
    s.supabase_key = "test-key"
    s.secret_key = SECRET_KEY
    s.algorithm = ALGORITHM
    s.access_token_expire = 15
    s.refresh_token_expire = 10080
    s.redis_url = "redis://localhost:6379/0"
    s.openai_api_key = "sk-test"
    s.embedding_model = "text-embedding-3-small"
    s.log_level = "INFO"
    s.environment = "test"
    s.cors_origins = ["http://localhost:5173"]
    return s


def make_token(sub="user-id", email="test@example.com", expire_minutes=15):
    payload = {
        "sub": sub,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture
def auth_client():
    mock_db = MagicMock()
    with patch("app.core.config.get_settings", return_value=make_settings()):
        from app.main import app
        from app.core.database import get_supabase_client

        app.dependency_overrides[get_supabase_client] = lambda: mock_db
        with TestClient(app) as c:
            yield c, mock_db
        app.dependency_overrides.pop(get_supabase_client, None)


def test_register_success(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "uid-1", "email": "novo@test.com", "nome": "Novo"}
    ]

    resp = client.post("/api/v1/auth/register", json={
        "email": "novo@test.com", "password": "senha123", "nome": "Novo"
    })

    assert resp.status_code == 201
    assert resp.json()["email"] == "novo@test.com"


def test_register_email_exists(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "uid-existing"}
    ]

    resp = client.post("/api/v1/auth/register", json={
        "email": "existente@test.com", "password": "senha123", "nome": "Existente"
    })

    assert resp.status_code == 400
    assert "já cadastrado" in resp.json()["detail"]


def test_login_success(auth_client):
    client, db = auth_client
    from app.core.security import hash_password
    hashed = hash_password("senha123")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "uid-1", "email": "user@test.com", "password_hash": hashed}
    ]

    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com", "password": "senha123"
    })

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_user_not_found(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.post("/api/v1/auth/login", json={
        "email": "naoexiste@test.com", "password": "senha123"
    })

    assert resp.status_code == 401


def test_login_wrong_password(auth_client):
    client, db = auth_client
    from app.core.security import hash_password
    hashed = hash_password("senha-correta")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "uid-1", "email": "user@test.com", "password_hash": hashed}
    ]

    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com", "password": "senha-errada"
    })

    assert resp.status_code == 401


def test_refresh_success(auth_client):
    client, _ = auth_client
    token = make_token()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body


def test_refresh_invalid_token(auth_client):
    client, _ = auth_client

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "token-invalido"})

    assert resp.status_code == 401


def test_get_current_user_invalid_token(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.execute.return_value.data = []

    resp = client.get(
        "/api/v1/obras/",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert resp.status_code == 401
