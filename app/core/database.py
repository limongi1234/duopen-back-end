from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from supabase import AsyncClient, Client, acreate_client, create_client

from app.core.config import get_settings
import logging

log = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_supabase_client() -> Client:
    settings = get_settings()
    try:
        return create_client(settings.supabase_url, settings.supabase_key)
    except Exception as exc:
        log.exception("Falha ao criar cliente Supabase")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar ao Supabase: {exc}",
        )


async def get_async_supabase_client() -> AsyncGenerator[AsyncClient, None]:
    settings = get_settings()
    try:
        client = await acreate_client(settings.supabase_url, settings.supabase_key)
        yield client
    except Exception as exc:
        log.exception("Falha ao criar cliente Supabase assíncrono")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar ao Supabase: {exc}",
        )


def init_db_engine() -> None:
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    log.info("SQLAlchemy async engine inicializado")


async def dispose_db_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        log.info("SQLAlchemy async engine encerrado")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Engine não inicializado — chame init_db_engine() no lifespan")
    async with _session_factory() as session:
        yield session


async def check_connection() -> dict[str, bool]:
    results: dict[str, bool] = {}

    try:
        client = get_supabase_client()
        client.table("raw_contratos").select("id").limit(1).execute()
        results["supabase"] = True
    except Exception as exc:
        log.error("Falha na conexão com Supabase: %s", exc)
        results["supabase"] = False

    if _engine is not None:
        try:
            async with _engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            results["database"] = True
        except Exception as exc:
            log.error("Falha na conexão direta com o banco: %s", exc)
            results["database"] = False

    return results
