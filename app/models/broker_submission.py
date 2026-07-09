"""Fact 2: BrokerSubmission — one row per entity × broker × coverage × period.

Monthly aggregated actuals, not policy-level transactions (SPEC §3.3).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

MONEY = Numeric(18, 2)


class BrokerSubmission(Base):
    __tablename__ = "broker_submissions"
    __table_args__ = (
        UniqueConstraint(
            "entity_code", "broker_id", "coverage", "period", name="uq_submission_natural_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    entity_code: Mapped[str] = mapped_column(ForeignKey("entities.entity_code"))
    broker_id: Mapped[str] = mapped_column(ForeignKey("brokers.broker_id"), index=True)
    coverage: Mapped[str] = mapped_column(ForeignKey("coverages.code"))
    region: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    quotes: Mapped[int] = mapped_column(Integer)
    binds: Mapped[int] = mapped_column(Integer)
    gwp: Mapped[Decimal] = mapped_column(MONEY)
    gwp_new: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    gwp_renewal: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    brokerage: Mapped[Decimal] = mapped_column(MONEY)
    total_limit: Mapped[Decimal] = mapped_column(MONEY)
    avg_premium_deviation: Mapped[float] = mapped_column(Float)
    breach_count_amber: Mapped[int] = mapped_column(Integer, default=0)
    breach_count_red: Mapped[int] = mapped_column(Integer, default=0)
    incurred_loss_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_client_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    top_client_limit: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    top_client_industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
