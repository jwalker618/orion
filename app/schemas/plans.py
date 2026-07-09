"""Request/response schemas for entity plans (SPEC §3.2, §4.1)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.schemas.common import (
    BatchReport,
    CoverageCode,
    Currency,
    Period,
    StrictModel,
    period_not_in_future,
)

Money = Field(ge=0, max_digits=18, decimal_places=2)


class EntityPlanIn(StrictModel):
    entity_code: str = Field(min_length=1, max_length=20)
    coverage: CoverageCode
    period: Period
    currency: Currency = "USD"
    plan_gwp: Decimal = Money
    plan_brokerage: Decimal = Money
    expected_hit_ratio: float = Field(ge=0, le=1)
    expected_bind_count: int | None = Field(default=None, ge=0)
    plan_loss_ratio: float = Field(ge=0, le=2)
    guardrail_low: Decimal = Field(gt=0, decimal_places=4)
    guardrail_high: Decimal = Field(gt=0, decimal_places=4)
    aggregate_limit: Decimal = Money
    notes: str | None = Field(default=None, max_length=500)

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

    @model_validator(mode="after")
    def _guardrail_order(self) -> "EntityPlanIn":
        if self.guardrail_high <= self.guardrail_low:
            raise ValueError("guardrail_high must be greater than guardrail_low")
        return self

    @property
    def natural_key(self) -> str:
        return f"{self.entity_code}/{self.coverage.value}/{self.period}"


class EntityPlanBatch(StrictModel):
    records: list[EntityPlanIn] = Field(min_length=1, max_length=500)


class EntityPlanOut(StrictModel):
    entity_code: str
    coverage: str
    period: str
    currency: str
    plan_gwp: Decimal
    plan_brokerage: Decimal
    expected_hit_ratio: float
    expected_bind_count: int | None
    plan_loss_ratio: float
    guardrail_low: Decimal
    guardrail_high: Decimal
    aggregate_limit: Decimal
    notes: str | None

    # Response convention (SPEC §4.2): money as decimal strings.
    @field_serializer("plan_gwp", "plan_brokerage", "aggregate_limit", "guardrail_low", "guardrail_high")
    def _dec_str(self, v: Decimal) -> str:
        return str(v)


class PlanBatchReport(BatchReport):
    pass
