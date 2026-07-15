"""Auth primitives — password hashing, signed access tokens, TOTP (RFC 6238).

Stdlib only, deliberately: the demo carries no crypto dependencies. The design
mirrors the generate-web auth contract (short-lived HMAC-signed access tokens,
opaque rotating refresh tokens, TOTP MFA). Production upgrade path: swap the
signer for a real JWT/JWKS issuer (Entra ID per SPEC §10) — the endpoint
shapes already match.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time

PBKDF2_ITERATIONS = 60_000


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


# --- access tokens (HMAC-signed, JWT-shaped claims) --------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_access_token(secret: str, user_id: str, ttl_seconds: int) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + ttl_seconds,
        "jti": secrets.token_hex(8),
        "type": "access",
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_access_token(secret: str, token: str) -> str | None:
    """Return the subject user_id, or None if invalid/expired."""
    try:
        body, sig = token.split(".")
        expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("type") != "access" or payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")
    except (ValueError, json.JSONDecodeError):
        return None


# --- refresh tokens (opaque; only the hash is stored) ------------------------


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- TOTP (RFC 6238, 30s step, 6 digits) -------------------------------------


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret_b32: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    counter = int((at if at is not None else time.time()) // step)
    msg = struct.pack(">Q", counter)
    mac = hmac.new(key, msg, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = (int.from_bytes(mac[offset : offset + 4], "big") & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def verify_totp(secret_b32: str, code: str, at: float | None = None, window: int = 1) -> bool:
    now = at if at is not None else time.time()
    return any(
        hmac.compare_digest(totp_code(secret_b32, now + drift * 30), code.strip())
        for drift in range(-window, window + 1)
    )


def otpauth_uri(secret_b32: str, account: str, issuer: str = "ORION") -> str:
    return (
        f"otpauth://totp/{issuer}:{account}?secret={secret_b32}"
        f"&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    )


def new_backup_codes(n: int = 8) -> list[str]:
    return [secrets.token_hex(4) for _ in range(n)]
