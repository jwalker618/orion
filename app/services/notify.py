"""Login notifications to Slack — the ORION port of generate-web DSI's
login-notify route.

Same contract: a SERVER-ONLY incoming-webhook URL (never reaches the browser),
one line per fresh login, best-effort by design — env unset means the feature
is off, and a Slack outage must never fail a login. Because ORION's backend
owns the login endpoint, the event fires server-side (no client round-trip).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import Request

from app.config import get_settings


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )


def send_login_notification(user, request: Request) -> None:
    """Post '🔓 ORION login — …' to the configured Slack webhook.

    Runs as a FastAPI background task after the login response is sent, so
    webhook latency never sits on the login path. All failures are swallowed.
    """
    url = get_settings().login_notify_webhook_url
    if not url:
        return

    label = user.display_name or user.email or "Someone"
    email_part = f" ({user.email})" if user.email and user.display_name else ""
    detail = " · ".join(p for p in (user.role, user.organisation) if p)
    ip = _client_ip(request)
    ua = (request.headers.get("user-agent") or "")[:140]
    stamp = datetime.now(timezone.utc).isoformat()
    text = (
        f"🔓 *ORION login* — {label}{email_part}{f' · {detail}' if detail else ''}\n"
        f"{ip} · {ua} · {stamp}"
    )

    try:
        httpx.post(url, json={"text": text}, timeout=5)
    except Exception:
        # Best-effort — a down/rotated webhook must never surface to the user.
        pass
