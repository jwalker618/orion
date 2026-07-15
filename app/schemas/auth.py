"""Auth request/response schemas — wire-compatible with the generate-web
auth adapter (packages/auth + apps/dsi/src/lib/api/auth.ts)."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import StrictModel


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenPair(StrictModel):
    access_token: str
    refresh_token: str
    expires_in_seconds: int


class LoginResponse(TokenPair):
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_setup_required: bool = False


class RefreshRequest(StrictModel):
    refresh_token: str


class LogoutRequest(StrictModel):
    refresh_token: str


class MeResponse(StrictModel):
    user_id: str
    email: str | None
    tenant_id: str
    role: str | None
    permissions: list[str]
    mfa_enabled: bool
    display_name: str | None = None
    job_title: str | None = None
    organisation: str | None = None
    entity_scope: str | None = None
    joined_at: str | None = None
    last_login: str | None = None
    review: bool | None = None


class MFAVerifyRequest(StrictModel):
    code: str = Field(min_length=6, max_length=16)


class MFASetupResponse(StrictModel):
    secret: str
    otpauth_uri: str


class BackupCodesResponse(StrictModel):
    codes: list[str]


class PasswordResetRequest(StrictModel):
    email: EmailStr


class PasswordResetConfirm(StrictModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=200)
