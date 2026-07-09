"""Request/response schemas for broker submissions and the broker registry."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_serializer, field_validator

from app.schemas.common import (
    CLIENT_REF_RE,
    BatchReport,
    BrokerTier,
    ClientIndustry,
    CoverageCode,
    Currency,
    Period,
    StrictModel,
    period_not_in_future,
)

Money = Field(ge=0, max_digits=18, decimal_places=2)
OptionalMoney = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class BrokerSubmissionIn(StrictModel):
    entity_code: str = Field(min_length=1, max_length=20)
    broker_id: str = Field(min_length=1, max_length=40)
    broker_name: str | None = Field(default=None, max_length=200)
    broker_group: str | None = Field(default=None, max_length=200)
    tier: BrokerTier | None = None
    coverage: CoverageCode
    region: str = Field(min_length=1, max_length=50)
    period: Period
    currency: Currency = "USD"
    quotes: int = Field(ge=0)
    binds: int = Field(ge=0)
    gwp: Decimal = Money
    gwp_new: Decimal | None = OptionalMoney
    gwp_renewal: Decimal | None = OptionalMoney
    brokerage: Decimal = Money
    total_limit: Decimal = Money
    avg_premium_deviation: float = Field(gt=0)
    breach_count_amber: int = Field(default=0, ge=0)
    breach_count_red: int = Field(default=0, ge=0)
    incurred_loss_ratio: float | None = Field(default=None, ge=0, le=5)
    top_client_ref: str | None = Field(default=None, max_length=40)
    top_client_limit: Decimal | None = OptionalMoney
    top_client_industry: ClientIndustry | None = None

    @field_validator("entity_code")
    @classmethod
    def _upper_entity(cls, v: str) -> str:
        return v.upper()

    @field_validator("period")
    @classmethod
    def _period_window(cls, v: str) -> str:
        if not period_not_in_future(v):
            raise ValueError("period must not be in the future beyond +1 month")
        return v

    @field_validator("top_client_ref")
    @classmethod
    def _privacy_guard(cls, v: str | None) -> str | None:
        # SPEC §5.9: only anonymised CL-xxxx codes; anything email/phone/name-like
        # fails the pattern and is rejected.
        if v is not None and not CLIENT_REF_RE.match(v):
            raise ValueError(
                "top_client_ref must be an anonymised code matching CL-xxxx (no PII)"
            )
        return v

    @property
    def natural_key(self) -> str:
        return f"{self.entity_code}/{self.broker_id}/{self.coverage.value}/{self.period}"


class BrokerSubmissionBatch(StrictModel):
    records: list[BrokerSubmissionIn] = Field(min_length=1, max_length=1000)


class BrokerSubmissionOut(StrictModel):
    entity_code: str
    broker_id: str
    coverage: str
    region: str
    period: str
    currency: str
    quotes: int
    binds: int
    gwp: Decimal
    gwp_new: Decimal | None
    gwp_renewal: Decimal | None
    brokerage: Decimal
    total_limit: Decimal
    avg_premium_deviation: float
    breach_count_amber: int
    breach_count_red: int
    incurred_loss_ratio: float | None
    top_client_ref: str | None
    top_client_limit: Decimal | None
    top_client_industry: str | None

    @field_serializer("gwp", "gwp_new", "gwp_renewal", "brokerage", "total_limit", "top_client_limit")
    def _dec_str(self, v: Decimal | None) -> str | None:
        return None if v is None else str(v)


class BrokerIn(StrictModel):
    broker_id: str = Field(min_length=1, max_length=40)
    broker_name: str = Field(min_length=1, max_length=200)
    broker_group: str | None = Field(default=None, max_length=200)
    tier: BrokerTier | None = None
    home_region: str | None = Field(default=None, max_length=50)
    is_new: bool = False


class BrokerBatch(StrictModel):
    records: list[BrokerIn] = Field(min_length=1, max_length=1000)


class SubmissionBatchReport(BatchReport):
    pass
