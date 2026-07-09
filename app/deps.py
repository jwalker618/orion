"""Shared FastAPI dependencies: API-key auth and the common list filters."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.schemas.common import PERIOD_RE

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if api_key is None or api_key not in get_settings().api_key_set:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return api_key


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
