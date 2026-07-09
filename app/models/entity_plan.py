"""Fact 1: EntityPlan — one row per entity × coverage × period (SPEC §3.2)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

MONEY = Numeric(18, 2)


class EntityPlan(Base):
    __tablename__ = "entity_plans"
    __table_args__ = (
        UniqueConstraint("entity_code", "coverage", "period", name="uq_plan_natural_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    entity_code: Mapped[str] = mapped_column(ForeignKey("entities.entity_code"))
    coverage: Mapped[str] = mapped_column(ForeignKey("coverages.code"))
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    plan_gwp: Mapped[Decimal] = mapped_column(MONEY)
    plan_brokerage: Mapped[Decimal] = mapped_column(MONEY)
    expected_hit_ratio: Mapped[float] = mapped_column(Float)
    expected_bind_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_loss_ratio: Mapped[float] = mapped_column(Float)
    guardrail_low: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    guardrail_high: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    aggregate_limit: Mapped[Decimal] = mapped_column(MONEY)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
