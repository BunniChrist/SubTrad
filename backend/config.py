from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CACHE_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "cache.db")


class Settings(BaseSettings):
    max_duration_seconds: int = 720
    cache_threshold: int = 100
    cache_db_path: str = DEFAULT_CACHE_DB_PATH
    supported_languages: list[str] = ["fr", "es", "en", "ja"]
    openai_api_key: str = ""
    youtube_api_key: str = ""
    proxy_url: str = ""

    model_config = SettingsConfigDict(env_prefix="subtrad_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
