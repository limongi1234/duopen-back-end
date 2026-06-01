from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.core.config.get_settings") as mock:
        settings = MagicMock()
        settings.secret_key = "test-secret-key-for-testing-minimum-32"
        settings.algorithm = "HS256"
        settings.access_token_expire = 15
        settings.refresh_token_expire = 10080
        mock.return_value = settings
        yield settings


def test_hash_and_verify_password():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("senha123")
    assert verify_password("senha123", hashed)
    assert not verify_password("errada", hashed)


def test_create_and_decode_access_token():
    from app.core.security import create_access_token, decode_token
    data = {"sub": "user-123", "email": "test@example.com"}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@example.com"


def test_create_and_decode_refresh_token():
    from app.core.security import create_refresh_token, decode_token
    data = {"sub": "user-456", "email": "refresh@example.com"}
    token = create_refresh_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == "user-456"
