"""Response schemas for the dashboard read model (SPEC §4.2).

Conventions: money as decimal strings alongside a currency; ratios as floats;
every aggregate response carries `as_of` and an echo of the applied filters.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Response models are lenient about extras we add later, but still typed.


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def money(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


class Kpi(DashboardModel):
    value: float | None
    mom_trend: float | None = None


class MoneyKpi(DashboardModel):
    value: str | None
    currency: str = "USD"
    mom_trend: float | None = None


class ExecutiveSeriesPoint(DashboardModel):
    period: str
    hit_ratio: float | None
    gwp: str
    plan_gwp: str


class TopBroker(DashboardModel):
    broker_id: str
    broker_name: str
    tier: str | None
    gwp: str
    hit_ratio: float | None


class Alert(DashboardModel):
    type: str
    severity: str
    entity_code: str | None = None
    coverage: str | None = None
    period: str | None = None
    broker_id: str | None = None
    message: str


class ExecutiveDashboard(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    kpis: dict[str, Kpi | MoneyKpi]
    series: list[ExecutiveSeriesPoint]
    top_brokers: list[TopBroker]
    alerts: list[Alert]


class BrokerLeaderboardRow(DashboardModel):
    broker_id: str
    broker_name: str
    broker_group: str | None
    tier: str | None
    home_region: str | None
    hit_ratio: float | None
    gwp: str
    brokerage: str
    avg_premium_deviation: float | None
    incurred_loss_ratio: float | None
    sparkline: list[float] = Field(description="12-month GWP series, oldest first")


class BrokerLeaderboard(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    total: int
    rows: list[BrokerLeaderboardRow]


class BrokerMonthPoint(DashboardModel):
    period: str
    quotes: int
    binds: int
    hit_ratio: float | None
    gwp: str
    brokerage: str
    avg_premium_deviation: float | None


class BrokerCoverageRow(DashboardModel):
    coverage: str
    gwp: str
    hit_ratio: float | None
    binds: int


class BrokerProfile(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    broker_id: str
    broker_name: str
    broker_group: str | None
    tier: str | None
    home_region: str | None
    is_new: bool
    share_of_wallet: float | None
    monthly: list[BrokerMonthPoint]
    coverages: list[BrokerCoverageRow]


class NamedExposure(DashboardModel):
    name: str
    total_limit: str
    gwp: str


class TopClient(DashboardModel):
    client_ref: str
    industry: str | None
    total_limit: str
    entity_code: str


class LorenzPoint(DashboardModel):
    x: float
    y: float


class ExposureDashboard(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    currency: str
    by_region: list[NamedExposure]
    by_coverage: list[NamedExposure]
    top_clients: list[TopClient]
    lorenz: list[LorenzPoint]
    gini: float | None
    alerts: list[Alert]


class HistogramBucket(DashboardModel):
    low: float | None
    high: float | None
    label: str
    count: int


class CoverageBreaches(DashboardModel):
    coverage: str
    amber: int
    red: int
    binds: int
    breach_pct: float | None


class BreachRow(DashboardModel):
    entity_code: str
    coverage: str
    period: str
    broker_id: str
    avg_premium_deviation: float
    guardrail_low: float | None
    guardrail_high: float | None
    breach_count_amber: int
    breach_count_red: int


class WhatIf(DashboardModel):
    threshold: float
    lower_band: float
    breached_rows: int
    breached_binds: int


class GuardrailsDashboard(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    histogram: list[HistogramBucket]
    by_coverage: list[CoverageBreaches]
    breach_list: list[BreachRow]
    what_if: WhatIf | None


class PlanVsActualRow(DashboardModel):
    entity_code: str
    coverage: str
    currency: str
    plan_gwp: str
    actual_gwp: str
    plan_attainment_gwp: float | None
    expected_hit_ratio: float | None
    hit_ratio: float | None
    hit_ratio_variance: float | None
    plan_loss_ratio: float | None
    incurred_loss_ratio: float | None
    loss_ratio_variance: float | None
    flags: list[str]


class PlanVsActual(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    rows: list[PlanVsActualRow]


class PagedResponse(DashboardModel):
    as_of: datetime
    filters: dict[str, Any]
    total: int
    limit: int
    offset: int
    records: list[Any]

    @field_serializer("records")
    def _records(self, v: list[Any]) -> list[Any]:
        return v
