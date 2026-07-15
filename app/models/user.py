"""Identity tables: users, rotating refresh tokens, password-reset tokens.

Mirrors the generate-web / DSI auth contract's user shape (role, permissions
derived from role, MFA, identity fields for the profile menu).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# role -> permissions. Machine callers (X-API-Key) implicitly hold all of them.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "group_admin": [
        "dashboard:read", "ingest:write", "reference:write", "admin:reset",
        "workflow:read", "market:read",
    ],
    "broker_relations": [
        "dashboard:read", "ingest:write", "reference:write",
        "workflow:read", "market:read",
    ],
    "entity_underwriter": ["dashboard:read", "workflow:read", "market:read"],
    "reviewer": ["dashboard:read"],
}


def permissions_for_role(role: str | None) -> list[str]:
    return ROLE_PERMISSIONS.get(role or "", [])


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    organisation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(40), default="msad")
    role: Mapped[str] = mapped_column(String(40), default="broker_relations")
    # Underwriters are scoped to their entity; the UI presets + locks the filter.
    entity_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backup_code_hashes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_reviewer(self) -> bool:
        return self.role == "reviewer"


class RefreshToken(Base):
    """Opaque rotating refresh tokens; only hashes are stored. Reuse of a
    rotated (revoked) token burns the whole family — stolen-token replay
    can't mint sessions."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    family: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
