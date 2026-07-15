"""Interactive auth — wire-compatible with the generate-web auth adapter.

POST /auth/login            {email, password} -> tokens (+ mfa_required)
POST /auth/refresh          rotating refresh; reuse burns the token family
POST /auth/logout           revokes the refresh token
GET  /auth/me               bearer -> profile with role + permissions
POST /auth/mfa/setup        bearer -> TOTP secret + otpauth URI
POST /auth/mfa/verify       bearer + {code} -> enables/passes MFA
POST /auth/mfa/backup-codes bearer -> fresh single-use codes
POST /auth/password/reset-request  always 204 (no account enumeration)
POST /auth/password/reset-confirm  {token, new_password}
GET  /auth/sso/{tenant}     501 until an IdP is configured (endpoint shape kept)
POST /auth/sso/callback     501 until an IdP is configured

Login is the only place MFA is *challenged*: when the user has MFA enabled the
token pair comes back with mfa_required=true and the access token is limited
to the /auth/* surface until /auth/mfa/verify passes (mirrors the DSI flow).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import RefreshToken, PasswordResetToken, User, permissions_for_role
from app.schemas import auth as s
from app.services import security
from app.services.notify import send_login_notification

router = APIRouter(prefix="/auth", tags=["auth"])

# In-flight MFA challenges: access-token jti isn't tracked, so we key the
# pending state on the user until verify passes. Demo-grade (in-process).
_pending_mfa: set[str] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _issue_pair(db: Session, user: User) -> s.LoginResponse:
    settings = get_settings()
    refresh = security.new_refresh_token()
    db.add(
        RefreshToken(
            token_sha256=security.token_hash(refresh),
            user_id=user.user_id,
            family=secrets.token_hex(8),
            expires_at=_now() + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    db.commit()
    return s.LoginResponse(
        access_token=security.issue_access_token(
            settings.auth_secret, user.user_id, settings.access_token_ttl_seconds
        ),
        refresh_token=refresh,
        expires_in_seconds=settings.access_token_ttl_seconds,
        mfa_required=user.mfa_enabled,
        mfa_setup_required=False,
    )


def _bearer_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    user_id = security.verify_access_token(
        get_settings().auth_secret, authorization[7:].strip()
    )
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    return user


def _bearer_user_mfa_passed(user: User = Depends(_bearer_user)) -> User:
    if user.user_id in _pending_mfa:
        raise HTTPException(status_code=401, detail="MFA verification required")
    return user


@router.post("/login", response_model=s.LoginResponse)
def login(
    body: s.LoginRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> s.LoginResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not security.verify_password(
        body.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.mfa_enabled:
        # The fresh-login notification waits for the MFA challenge to pass.
        _pending_mfa.add(user.user_id)
    else:
        user.last_login = _now()
        background.add_task(send_login_notification, user, request)
    return _issue_pair(db, user)


@router.post("/refresh", response_model=s.TokenPair)
def refresh(body: s.RefreshRequest, db: Session = Depends(get_db)) -> s.TokenPair:
    settings = get_settings()
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_sha256 == security.token_hash(body.refresh_token)
        )
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Unknown refresh token")
    if row.revoked:
        # Rotated-token replay: burn the whole family (stolen-token defence).
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family == row.family)
            .values(revoked=True)
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected")
    if row.expires_at < _now():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    row.revoked = True
    new_refresh = security.new_refresh_token()
    db.add(
        RefreshToken(
            token_sha256=security.token_hash(new_refresh),
            user_id=user.user_id,
            family=row.family,
            expires_at=_now() + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    db.commit()
    return s.TokenPair(
        access_token=security.issue_access_token(
            settings.auth_secret, user.user_id, settings.access_token_ttl_seconds
        ),
        refresh_token=new_refresh,
        expires_in_seconds=settings.access_token_ttl_seconds,
    )


@router.post("/logout", status_code=204)
def logout(body: s.LogoutRequest, db: Session = Depends(get_db)) -> Response:
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_sha256 == security.token_hash(body.refresh_token)
        )
    )
    if row:
        row.revoked = True
        _pending_mfa.discard(row.user_id)
        db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=s.MeResponse)
def me(user: User = Depends(_bearer_user_mfa_passed)) -> s.MeResponse:
    return s.MeResponse(
        user_id=user.user_id,
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        permissions=permissions_for_role(user.role),
        mfa_enabled=user.mfa_enabled,
        display_name=user.display_name,
        job_title=user.job_title,
        organisation=user.organisation,
        entity_scope=user.entity_scope,
        joined_at=user.joined_at.isoformat() if user.joined_at else None,
        last_login=user.last_login.isoformat() if user.last_login else None,
        review=user.is_reviewer or None,
    )


@router.post("/mfa/setup", response_model=s.MFASetupResponse)
def mfa_setup(
    user: User = Depends(_bearer_user_mfa_passed), db: Session = Depends(get_db)
) -> s.MFASetupResponse:
    secret = security.new_totp_secret()
    user.mfa_secret = secret
    # Not enabled until the first successful verify proves the authenticator.
    db.commit()
    return s.MFASetupResponse(
        secret=secret, otpauth_uri=security.otpauth_uri(secret, user.email or user.user_id)
    )


@router.post("/mfa/verify")
def mfa_verify(
    body: s.MFAVerifyRequest,
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(_bearer_user),
    db: Session = Depends(get_db),
) -> dict:
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not set up for this account")

    ok = security.verify_totp(user.mfa_secret, body.code)
    if not ok and user.backup_code_hashes:
        hashes = json.loads(user.backup_code_hashes)
        candidate = security.token_hash(body.code.strip())
        if candidate in hashes:
            hashes.remove(candidate)  # single-use
            user.backup_code_hashes = json.dumps(hashes)
            ok = True
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    was_login_challenge = user.user_id in _pending_mfa
    user.mfa_enabled = True
    user.last_login = _now()
    _pending_mfa.discard(user.user_id)
    db.commit()
    if was_login_challenge:
        # This verify completed a sign-in (not an enrollment) — notify now.
        background.add_task(send_login_notification, user, request)
    return {"verified": True}


@router.post("/mfa/backup-codes", response_model=s.BackupCodesResponse)
def mfa_backup_codes(
    user: User = Depends(_bearer_user_mfa_passed), db: Session = Depends(get_db)
) -> s.BackupCodesResponse:
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not set up for this account")
    codes = security.new_backup_codes()
    user.backup_code_hashes = json.dumps([security.token_hash(c) for c in codes])
    db.commit()
    return s.BackupCodesResponse(codes=codes)


@router.post("/password/reset-request", status_code=204)
def password_reset_request(
    body: s.PasswordResetRequest, db: Session = Depends(get_db)
) -> Response:
    # Always 204 — no account enumeration. The demo has no mailer: the token
    # lands in the server log (documented in DEPLOY.md).
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user:
        token = security.new_refresh_token()
        db.add(
            PasswordResetToken(
                token_sha256=security.token_hash(token),
                user_id=user.user_id,
                expires_at=_now()
                + timedelta(seconds=get_settings().password_reset_ttl_seconds),
            )
        )
        db.commit()
        print(f"[orion-auth] password reset for {user.email}: token={token}", flush=True)
    return Response(status_code=204)


@router.post("/password/reset-confirm", status_code=204)
def password_reset_confirm(
    body: s.PasswordResetConfirm, db: Session = Depends(get_db)
) -> Response:
    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_sha256 == security.token_hash(body.token)
        )
    )
    if row is None or row.used or row.expires_at < _now():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = security.hash_password(body.new_password)
    row.used = True
    # New credential invalidates every live session.
    db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.user_id).values(revoked=True)
    )
    db.commit()
    return Response(status_code=204)


@router.get("/sso/{tenant_slug}")
def sso_start(tenant_slug: str) -> dict:
    raise HTTPException(
        status_code=501,
        detail="SSO is not configured in the demo; the endpoint shape matches the "
        "generate-web contract so an IdP can be wired without frontend changes.",
    )


@router.post("/sso/callback")
def sso_callback() -> dict:
    raise HTTPException(status_code=501, detail="SSO is not configured in the demo")
