"""Application settings.

Everything demo-tunable comes from the environment (or a local .env), with
safe defaults so `uvicorn app.main:app` starts with zero configuration.
Swap to Postgres by pointing DATABASE_URL at a Postgres DSN.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
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

    # --- interactive auth (generate-web contract) ---
    # HMAC secret for access tokens. Override in any real deployment; the
    # default only exists so the demo boots with zero config.
    auth_secret: str = "orion-demo-auth-secret"
    # Password every seeded demo user starts with.
    demo_password: str = "orion-demo"
    access_token_ttl_seconds: int = 15 * 60
    # Slack incoming-webhook for login notifications (generate-web DSI
    # pattern; server-only, best-effort). Accepts either the ORION_-prefixed
    # name or the bare LOGIN_NOTIFY_WEBHOOK_URL used by the DSI Vercel project.
    login_notify_webhook_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ORION_LOGIN_NOTIFY_WEBHOOK_URL", "LOGIN_NOTIFY_WEBHOOK_URL"
        ),
    )
    # Sliding refresh window — mirrors the 45-minute idle limit the frontend
    # session guard enforces; each rotation extends it.
    refresh_token_ttl_seconds: int = 45 * 60
    password_reset_ttl_seconds: int = 30 * 60

    @property
    def api_key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
