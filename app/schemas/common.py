"""Shared vocabulary and field rules for all request/response schemas."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CoverageCode(str, Enum):
    PROPERTY = "PROPERTY"
    CASUALTY = "CASUALTY"
    MARINE = "MARINE"
    ENERGY = "ENERGY"
    CYBER = "CYBER"
    DO = "DO"
    PI = "PI"
    FI = "FI"


class BrokerTier(str, Enum):
    PLATINUM = "PLATINUM"
    GOLD = "GOLD"
    SILVER = "SILVER"
    BRONZE = "BRONZE"


class ClientIndustry(str, Enum):
    MANUFACTURING = "MANUFACTURING"
    FINANCIAL_SERVICES = "FINANCIAL_SERVICES"
    ENERGY = "ENERGY"
    TECHNOLOGY = "TECHNOLOGY"
    HEALTHCARE = "HEALTHCARE"
    RETAIL = "RETAIL"
    TRANSPORT = "TRANSPORT"
    CONSTRUCTION = "CONSTRUCTION"
    REAL_ESTATE = "REAL_ESTATE"
    OTHER = "OTHER"


PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Privacy guard (SPEC §5.9): client refs must be anonymised CL-xxxx codes.
# Anything email-, phone- or name-like fails this pattern and is rejected.
CLIENT_REF_RE = re.compile(r"^CL-[A-Za-z0-9_-]{2,32}$")

Period = Annotated[str, Field(pattern=PERIOD_RE.pattern, description="ISO month, YYYY-MM")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", description="ISO-4217 code")]


def period_not_in_future(period: str, today: date | None = None) -> bool:
    """Period must not be in the future beyond +1 month (SPEC §5.8)."""
    today = today or datetime.now(timezone.utc).date()
    year, month = int(period[:4]), int(period[5:7])
    next_month = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
    return (year, month) <= next_month


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RejectedRecord(StrictModel):
    index: int
    key: str
    errors: list[str]


class BatchReport(StrictModel):
    """Upsert-and-report envelope returned by every ingestion POST (SPEC §4.1)."""

    accepted: int
    updated: int
    rejected: list[RejectedRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
