from unittest.mock import MagicMock, patch

from app.core import locks


def test_acquire_lock_sucesso():
    client = MagicMock()
    client.set.return_value = True
    with patch("app.core.locks._client", return_value=client):
        assert locks.acquire_lock("k", 10) is True
    client.set.assert_called_once_with("k", "1", nx=True, ex=10)


def test_acquire_lock_ja_existe():
    client = MagicMock()
    client.set.return_value = None  # NX falhou (já existe)
    with patch("app.core.locks._client", return_value=client):
        assert locks.acquire_lock("k", 10) is False


def test_acquire_lock_redis_indisponivel_nao_bloqueia():
    with patch("app.core.locks._client", side_effect=RuntimeError("no redis")):
        assert locks.acquire_lock("k", 10) is True


def test_release_lock_chama_delete():
    client = MagicMock()
    with patch("app.core.locks._client", return_value=client):
        locks.release_lock("k")
    client.delete.assert_called_once_with("k")


def test_release_lock_resiliente():
    with patch("app.core.locks._client", side_effect=RuntimeError("no redis")):
        locks.release_lock("k")  # não deve levantar
