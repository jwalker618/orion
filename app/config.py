"""Application settings.

Everything demo-tunable comes from the environment (or a local .env), with
safe defaults so `uvicorn app.main:app` starts with zero configuration.
Swap to Postgres by pointing DATABASE_URL at a Postgres DSN.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ORION_", extra="ignore")

    database_url: str = "sqlite:///./demo.db"
    # Comma-separated list of accepted API keys (demo-grade auth stub).
    api_keys: str = "demo-key"
    cors_origins: str = "*"

    @property
    def api_key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
