import pytest
from unittest.mock import patch, MagicMock


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


@pytest.mark.asyncio
async def test_check_connection_success():
    with patch("app.core.database.get_supabase_client") as mock_get:
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_get.return_value = mock_client

        from app.core.database import check_connection
        result = await check_connection()

    assert result is True


@pytest.mark.asyncio
async def test_check_connection_failure():
    with patch("app.core.database.get_supabase_client") as mock_get:
        mock_get.side_effect = Exception("connection refused")

        from app.core.database import check_connection
        result = await check_connection()

    assert result is False
