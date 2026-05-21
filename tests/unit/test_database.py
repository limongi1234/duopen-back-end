import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Sync Supabase client ──────────────────────────────────────────────────────

def test_get_supabase_client():
    with patch("app.core.database.get_settings") as mock_settings, \
         patch("app.core.database.create_client") as mock_create:
        s = MagicMock()
        s.supabase_url = "https://test.supabase.co"
        s.supabase_key = "test-key"
        mock_settings.return_value = s
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        from app.core.database import get_supabase_client
        client = get_supabase_client()

        mock_create.assert_called_once_with("https://test.supabase.co", "test-key")
        assert client is mock_client


# ── Async Supabase client ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_async_supabase_client():
    with patch("app.core.database.get_settings") as mock_settings, \
         patch("app.core.database.acreate_client", new_callable=AsyncMock) as mock_acreate:
        s = MagicMock()
        s.supabase_url = "https://test.supabase.co"
        s.supabase_key = "test-key"
        mock_settings.return_value = s
        mock_client = MagicMock()
        mock_acreate.return_value = mock_client

        from app.core.database import get_async_supabase_client
        gen = get_async_supabase_client()
        client = await gen.__anext__()

        mock_acreate.assert_called_once_with("https://test.supabase.co", "test-key")
        assert client is mock_client


@pytest.mark.asyncio
async def test_get_async_supabase_client_error():
    from fastapi import HTTPException
    with patch("app.core.database.get_settings") as mock_settings, \
         patch("app.core.database.acreate_client", new_callable=AsyncMock) as mock_acreate:
        mock_settings.return_value = MagicMock(
            supabase_url="https://test.supabase.co",
            supabase_key="bad-key",
        )
        mock_acreate.side_effect = Exception("connection refused")

        from app.core.database import get_async_supabase_client
        with pytest.raises(HTTPException) as exc_info:
            await get_async_supabase_client().__anext__()

        assert exc_info.value.status_code == 500


# ── SQLAlchemy engine ─────────────────────────────────────────────────────────

def test_init_db_engine():
    import app.core.database as db_module
    saved_engine = db_module._engine
    saved_factory = db_module._session_factory

    with patch("app.core.database.get_settings") as mock_settings, \
         patch("app.core.database.create_async_engine") as mock_engine_fn, \
         patch("app.core.database.async_sessionmaker") as mock_factory_fn:
        s = MagicMock()
        s.database_url = "postgresql+asyncpg://test"
        mock_settings.return_value = s
        mock_engine = MagicMock()
        mock_engine_fn.return_value = mock_engine

        try:
            db_module.init_db_engine()

            mock_engine_fn.assert_called_once_with(
                "postgresql+asyncpg://test",
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
            mock_factory_fn.assert_called_once_with(mock_engine, expire_on_commit=False)
        finally:
            db_module._engine = saved_engine
            db_module._session_factory = saved_factory


@pytest.mark.asyncio
async def test_dispose_db_engine():
    import app.core.database as db_module
    mock_engine = AsyncMock()
    db_module._engine = mock_engine

    try:
        from app.core.database import dispose_db_engine
        await dispose_db_engine()

        mock_engine.dispose.assert_called_once()
        assert db_module._engine is None
    finally:
        db_module._engine = None


@pytest.mark.asyncio
async def test_dispose_db_engine_noop_when_none():
    import app.core.database as db_module
    db_module._engine = None

    from app.core.database import dispose_db_engine
    await dispose_db_engine()  # deve silenciosamente não fazer nada


# ── Session ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_db_session():
    import app.core.database as db_module
    mock_session = MagicMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    saved = db_module._session_factory
    db_module._session_factory = mock_factory

    try:
        from app.core.database import get_db_session
        gen = get_db_session()
        session = await gen.__anext__()
        assert session is mock_session
    finally:
        db_module._session_factory = saved


@pytest.mark.asyncio
async def test_get_db_session_raises_when_not_initialized():
    import app.core.database as db_module
    saved = db_module._session_factory
    db_module._session_factory = None

    try:
        from app.core.database import get_db_session
        with pytest.raises(RuntimeError, match="Engine não inicializado"):
            await get_db_session().__anext__()
    finally:
        db_module._session_factory = saved


# ── check_connection ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_connection_supabase_ok():
    import app.core.database as db_module
    saved_engine = db_module._engine
    db_module._engine = None  # sem engine, só testa supabase

    with patch("app.core.database.get_supabase_client") as mock_get:
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_get.return_value = mock_client

        from app.core.database import check_connection
        result = await check_connection()

    db_module._engine = saved_engine
    assert result == {"supabase": True}


@pytest.mark.asyncio
async def test_check_connection_supabase_and_db_ok():
    import app.core.database as db_module
    mock_conn = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_cm
    saved_engine = db_module._engine
    db_module._engine = mock_engine

    with patch("app.core.database.get_supabase_client") as mock_get:
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_get.return_value = mock_client

        from app.core.database import check_connection
        result = await check_connection()

    db_module._engine = saved_engine
    assert result == {"supabase": True, "database": True}


@pytest.mark.asyncio
async def test_check_connection_failure():
    import app.core.database as db_module
    saved_engine = db_module._engine
    db_module._engine = None

    with patch("app.core.database.get_supabase_client") as mock_get:
        mock_get.side_effect = Exception("connection refused")

        from app.core.database import check_connection
        result = await check_connection()

    db_module._engine = saved_engine
    assert result == {"supabase": False}
