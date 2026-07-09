"""Reference dimensions: entities, coverages, broker registry (SPEC §3.1)."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Entity(Base):
    """Reporting business unit — closed list, seeded (SPEC rule 5)."""

    __tablename__ = "entities"

    entity_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(50))


class Coverage(Base):
    """Line of business — controlled vocabulary."""

    __tablename__ = "coverages"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), default="")


class Broker(Base):
    """Broker registry; upserted on first sight or via POST /reference/brokers."""

    __tablename__ = "brokers"

    broker_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    broker_name: Mapped[str] = mapped_column(String(200))
    broker_group: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    home_region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
