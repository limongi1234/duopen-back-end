from supabase import create_client, Client
from app.core.config import get_settings
import logging

log = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


async def check_connection() -> bool:
    try:
        client = get_supabase_client()
        client.table("ingestoes").select("id").limit(1).execute()
        return True
    except Exception as e:
        log.error(f"Falha na conexão com Supabase: {e}")
        return False
