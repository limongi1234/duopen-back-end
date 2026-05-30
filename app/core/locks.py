"""Locks distribuídos simples via Redis (SET NX EX).

Usado para evitar execuções concorrentes de jobs pesados (ex.: indexação de
embeddings). Resiliente: se o Redis estiver indisponível, `acquire_lock` degrada
para "sem lock" (retorna True) em vez de derrubar a operação.
"""
import logging

import redis

from app.core.config import get_settings

log = logging.getLogger(__name__)


def _client() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
    )


def acquire_lock(key: str, ttl: int) -> bool:
    """Tenta adquirir o lock (atômico, com expiração). True se conseguiu."""
    try:
        return bool(_client().set(key, "1", nx=True, ex=ttl))
    except Exception as exc:  # Redis fora do ar não deve bloquear o job
        log.warning("Lock indisponível (%s); seguindo sem lock: %s", key, exc)
        return True


def release_lock(key: str) -> None:
    """Libera o lock. Silencioso em caso de falha (o TTL é a rede de segurança)."""
    try:
        _client().delete(key)
    except Exception as exc:
        log.warning("Falha ao liberar lock (%s): %s", key, exc)
