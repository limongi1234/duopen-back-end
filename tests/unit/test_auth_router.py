import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, timezone

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
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _ok_result(data=None):
    r = MagicMock()
    r.error = None
    r.data = data if data is not None else []
    return r


@pytest.fixture
def auth_client():
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result()
    mock_db.table.return_value.insert.return_value.execute.return_value = _ok_result()
    with patch("app.core.security.settings", make_settings()), \
         patch("app.core.database.init_db_engine"), \
         patch("app.core.database.dispose_db_engine"):
        from app.main import app
        from app.core.database import get_supabase_client

        app.dependency_overrides[get_supabase_client] = lambda: mock_db
        with TestClient(app) as c:
            yield c, mock_db
        app.dependency_overrides.pop(get_supabase_client, None)


def test_register_success(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([])
    db.table.return_value.insert.return_value.execute.return_value = _ok_result([
        {"id": "uid-1", "email": "novo@test.com", "nome": "Novo"}
    ])

    resp = client.post("/api/v1/auth/register", json={
        "email": "novo@test.com", "password": "senha123", "nome": "Novo"
    })

    assert resp.status_code == 201
    assert resp.json()["email"] == "novo@test.com"
    # novo usuário nasce com menor privilégio
    assert resp.json()["perfil"] == "readonly"
    # perfil enviado ao insert é readonly (não aceita escalada via body)
    assert db.table.return_value.insert.call_args[0][0]["perfil"] == "readonly"


def test_register_email_exists(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([
        {"id": "uid-existing"}
    ])

    resp = client.post("/api/v1/auth/register", json={
        "email": "existente@test.com", "password": "senha123", "nome": "Existente"
    })

    assert resp.status_code == 400
    assert "já cadastrado" in resp.json()["detail"]


def test_login_success(auth_client):
    client, db = auth_client
    from app.core.security import hash_password
    hashed = hash_password("senha123")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([
        {"id": "uid-1", "email": "user@test.com", "senha_hash": hashed}
    ])

    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com", "password": "senha123"
    })

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_user_not_found(auth_client):
    client, db = auth_client
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([])

    resp = client.post("/api/v1/auth/login", json={
        "email": "naoexiste@test.com", "password": "senha123"
    })

    assert resp.status_code == 401


def test_login_wrong_password(auth_client):
    client, db = auth_client
    from app.core.security import hash_password
    hashed = hash_password("senha-correta")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([
        {"id": "uid-1", "email": "user@test.com", "senha_hash": hashed}
    ])

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
    db.table.return_value.select.return_value.execute.return_value = _ok_result([])

    resp = client.get(
        "/api/v1/obras/",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert resp.status_code == 401


def test_me_success(auth_client):
    client, db = auth_client
    token = make_token(sub="uid-1", email="user@test.com")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([
        {"id": "uid-1", "email": "user@test.com", "nome": "User", "perfil": "gestor"}
    ])

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "uid-1"
    assert body["email"] == "user@test.com"
    assert body["nome"] == "User"
    assert body["perfil"] == "gestor"


def test_me_user_not_found(auth_client):
    client, db = auth_client
    token = make_token(sub="uid-ghost")
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = _ok_result([])

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 404


def test_me_invalid_token(auth_client):
    client, _ = auth_client

    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token-invalido"})

    assert resp.status_code == 401
