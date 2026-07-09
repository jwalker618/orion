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
    # Comma-separated allowed origins, or "*".
    cors_origins: str = "*"
    # Load the synthetic demo set at boot when the DB has no submissions —
    # keeps ephemeral-filesystem deploys (Railway without a volume) demo-ready.
    seed_on_start: bool = False

    @property
    def api_key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
