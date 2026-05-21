from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    supabase_url: str
    supabase_key: str

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire: int = 15
    refresh_token_expire: int = 10080

    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"

    log_level: str = "INFO"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
