from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    supabase_url: str
    supabase_key: str

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire: int = 15
    refresh_token_expire: int = 10080

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    redis_url: str = "redis://localhost:6379/0"

    # ── IA / RAG (stack gratuita: HuggingFace local + Gemini) ──────────────────
    # Embeddings locais (384 dims) — casa com VECTOR(384) da tabela `embeddings`.
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    google_api_key: Optional[str] = None
    llm_model: str = "gemini-2.5-flash-lite"
    rag_top_k: int = 5
    rag_temperature: float = 0.3

    # Mantido opcional para compatibilidade; a stack de IA não usa mais OpenAI.
    openai_api_key: Optional[str] = None

    log_level: str = "INFO"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
