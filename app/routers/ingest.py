"""Ingestion endpoints (SPEC §4.1): the two fact POSTs plus the broker registry.

Batches are received as raw dicts and validated record-by-record so one bad
record rejects itself, not the batch (partial acceptance with itemised,
field-level errors). Upserts are by natural key, making re-POSTs idempotent.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthDep
from app.models import Broker, BrokerSubmission, Entity, EntityPlan
from app.schemas.common import BatchReport, RejectedRecord, StrictModel
from app.schemas.plans import EntityPlanIn
from app.schemas.submissions import BrokerIn, BrokerSubmissionIn
from app.services import validation

router = APIRouter(tags=["ingestion"], dependencies=[AuthDep])


class RawPlanBatch(StrictModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class RawSubmissionBatch(StrictModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class RawBrokerBatch(StrictModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


def _pydantic_errors(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in err['loc']) or '<record>'}: {err['msg']}"
        for err in exc.errors()
    ]


def _guess_key(raw: dict[str, Any], fields: list[str]) -> str:
    return "/".join(str(raw.get(f, "?")) for f in fields)


@router.post("/entity-plans", response_model=BatchReport)
def post_entity_plans(batch: RawPlanBatch, db: Session = Depends(get_db)) -> BatchReport:
    known_entities = set(db.scalars(select(Entity.entity_code)))
    report = BatchReport(accepted=0, updated=0)

    for index, raw in enumerate(batch.records):
        try:
            record = EntityPlanIn.model_validate(raw)
        except ValidationError as exc:
            report.rejected.append(
                RejectedRecord(
                    index=index,
                    key=_guess_key(raw, ["entity_code", "coverage", "period"]),
                    errors=_pydantic_errors(exc),
                )
            )
            continue

        errors, warnings = validation.validate_plan(record, known_entities)
        report.warnings.extend(warnings)
        if errors:
            report.rejected.append(RejectedRecord(index=index, key=record.natural_key, errors=errors))
            continue

        existing = db.scalar(
            select(EntityPlan).where(
                EntityPlan.entity_code == record.entity_code,
                EntityPlan.coverage == record.coverage.value,
                EntityPlan.period == record.period,
            )
        )
        values = record.model_dump()
        values["coverage"] = record.coverage.value
        if existing:
            for field_name, value in values.items():
                setattr(existing, field_name, value)
            report.updated += 1
        else:
            db.add(EntityPlan(**values))
            report.accepted += 1

    db.commit()
    return report


@router.post("/broker-submissions", response_model=BatchReport)
def post_broker_submissions(
    batch: RawSubmissionBatch, db: Session = Depends(get_db)
) -> BatchReport:
    known_entities = set(db.scalars(select(Entity.entity_code)))
    known_brokers = set(db.scalars(select(Broker.broker_id)))
    report = BatchReport(accepted=0, updated=0)

    for index, raw in enumerate(batch.records):
        try:
            record = BrokerSubmissionIn.model_validate(raw)
        except ValidationError as exc:
            report.rejected.append(
                RejectedRecord(
                    index=index,
                    key=_guess_key(raw, ["entity_code", "broker_id", "coverage", "period"]),
                    errors=_pydantic_errors(exc),
                )
            )
            continue

        errors, warnings = validation.validate_submission(record, known_entities, known_brokers)
        report.warnings.extend(warnings)
        if errors:
            report.rejected.append(RejectedRecord(index=index, key=record.natural_key, errors=errors))
            continue

        # Registry upsert: auto-register unknown brokers, refresh known ones
        # with any registry fields supplied on the submission (SPEC §3.1).
        broker = db.get(Broker, record.broker_id)
        if broker is None:
            db.add(
                Broker(
                    broker_id=record.broker_id,
                    broker_name=record.broker_name or record.broker_id,
                    broker_group=record.broker_group,
                    tier=record.tier.value if record.tier else None,
                    home_region=record.region,
                    is_new=True,
                )
            )
            # Flush so a later record for the same broker in this batch sees it.
            db.flush()
            known_brokers.add(record.broker_id)
        else:
            if record.broker_name:
                broker.broker_name = record.broker_name
            if record.broker_group:
                broker.broker_group = record.broker_group
            if record.tier:
                broker.tier = record.tier.value

        existing = db.scalar(
            select(BrokerSubmission).where(
                BrokerSubmission.entity_code == record.entity_code,
                BrokerSubmission.broker_id == record.broker_id,
                BrokerSubmission.coverage == record.coverage.value,
                BrokerSubmission.period == record.period,
            )
        )
        values = record.model_dump(exclude={"broker_name", "broker_group", "tier"})
        values["coverage"] = record.coverage.value
        if record.top_client_industry:
            values["top_client_industry"] = record.top_client_industry.value
        if existing:
            for field_name, value in values.items():
                setattr(existing, field_name, value)
            report.updated += 1
        else:
            db.add(BrokerSubmission(**values))
            report.accepted += 1

    db.commit()
    return report


@router.post("/reference/brokers", response_model=BatchReport)
def post_reference_brokers(batch: RawBrokerBatch, db: Session = Depends(get_db)) -> BatchReport:
    report = BatchReport(accepted=0, updated=0)

    for index, raw in enumerate(batch.records):
        try:
            record = BrokerIn.model_validate(raw)
        except ValidationError as exc:
            report.rejected.append(
                RejectedRecord(
                    index=index,
                    key=_guess_key(raw, ["broker_id"]),
                    errors=_pydantic_errors(exc),
                )
            )
            continue

        values = record.model_dump()
        if record.tier:
            values["tier"] = record.tier.value
        broker = db.get(Broker, record.broker_id)
        if broker:
            for field_name, value in values.items():
                setattr(broker, field_name, value)
            report.updated += 1
        else:
            db.add(Broker(**values))
            report.accepted += 1

    db.commit()
    return report
