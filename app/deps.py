"""Shared FastAPI dependencies: auth (API key or bearer) and list filters.

Two caller kinds, mirroring the generate-web split:
- Machines (reporting-entity feeds, the seed script, curl) present X-API-Key
  and implicitly hold every permission.
- People present a Bearer access token issued by /api/v1/auth/login; their
  permissions derive from their role (app.models.user.ROLE_PERMISSIONS).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from fastapi import Depends, Header, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.common import PERIOD_RE
from app.services import security

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class AuthContext:
    kind: str                      # "machine" | "user"
    user_id: str | None = None
    role: str | None = None
    permissions: list[str] = field(default_factory=list)

    def has(self, permission: str) -> bool:
        return self.kind == "machine" or permission in self.permissions


def authenticate(
    api_key: str | None = Security(api_key_header),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthContext:
    if api_key is not None and api_key in get_settings().api_key_set:
        return AuthContext(kind="machine")

    if authorization and authorization.lower().startswith("bearer "):
        from app.models.user import User, permissions_for_role

        token = authorization[7:].strip()
        user_id = security.verify_access_token(get_settings().auth_secret, token)
        if user_id:
            user = db.get(User, user_id)
            if user and user.is_active:
                return AuthContext(
                    kind="user",
                    user_id=user.user_id,
                    role=user.role,
                    permissions=permissions_for_role(user.role),
                )
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    raise HTTPException(
        status_code=401, detail="Provide X-API-Key or a Bearer access token"
    )


def require_permission(permission: str):
    def checker(ctx: AuthContext = Depends(authenticate)) -> AuthContext:
        if not ctx.has(permission):
            raise HTTPException(
                status_code=403, detail=f"Requires the '{permission}' permission"
            )
        return ctx

    return checker


# Back-compat name: any authenticated caller (machine or user).
def require_api_key(ctx: AuthContext = Depends(authenticate)) -> AuthContext:
    return ctx


def _check_period(value: str | None, name: str) -> str | None:
    if value is not None and not PERIOD_RE.match(value):
        raise HTTPException(status_code=422, detail=f"{name} must be an ISO month (YYYY-MM)")
    return value


@dataclass
class ListFilters:
    """Query filters shared by every list GET (SPEC §4)."""

    entity: str | None = None
    coverage: str | None = None
    region: str | None = None
    tier: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    limit: int = 100
    offset: int = 0

    def echo(self) -> dict:
        """Applied-filters echo for response bodies."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def list_filters(
    entity: str | None = Query(default=None),
    coverage: str | None = Query(default=None),
    region: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    period_from: str | None = Query(default=None),
    period_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> ListFilters:
    return ListFilters(
        entity=entity.upper() if entity else None,
        coverage=coverage.upper() if coverage else None,
        region=region,
        tier=tier.upper() if tier else None,
        period_from=_check_period(period_from, "period_from"),
        period_to=_check_period(period_to, "period_to"),
        limit=limit,
        offset=offset,
    )


AuthDep = Depends(require_api_key)
FiltersDep = Depends(list_filters)
