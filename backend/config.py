from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    max_duration_seconds: int = 720
    cache_threshold: int = 100
    supported_languages: list[str] = ["fr", "es", "en", "ja"]
    openai_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="subtrad_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
