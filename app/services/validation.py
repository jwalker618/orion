"""Cross-field business rules (SPEC §5) that go beyond per-field Pydantic checks.

Each function returns (errors, warnings) for one record; the ingestion router
turns errors into per-record rejections and surfaces warnings in the batch
report. Rules needing reference data take pre-fetched sets so they stay pure.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.plans import EntityPlanIn
from app.schemas.submissions import BrokerSubmissionIn

GWP_SPLIT_TOLERANCE = Decimal("0.01")  # ±1% (SPEC §5.3)


def validate_plan(
    record: EntityPlanIn, known_entities: set[str]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if record.entity_code not in known_entities:
        errors.append(f"unknown entity_code '{record.entity_code}' (entities are a closed list)")

    # SPEC §5.4 — sanity warning, accepted.
    if not (record.guardrail_low < 1 <= record.guardrail_high):
        warnings.append(
            f"{record.natural_key}: guardrail band [{record.guardrail_low}, "
            f"{record.guardrail_high}] does not satisfy low < 1.0 <= high"
        )
    return errors, warnings


def validate_submission(
    record: BrokerSubmissionIn,
    known_entities: set[str],
    known_brokers: set[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if record.entity_code not in known_entities:
        errors.append(f"unknown entity_code '{record.entity_code}' (entities are a closed list)")

    # SPEC §5.2
    if record.binds > record.quotes:
        errors.append(f"binds ({record.binds}) must be <= quotes ({record.quotes})")

    # SPEC §5.3 — new + renewal within ±1% of gwp when all three present.
    if record.gwp_new is not None and record.gwp_renewal is not None:
        split = record.gwp_new + record.gwp_renewal
        tolerance = record.gwp * GWP_SPLIT_TOLERANCE
        if abs(split - record.gwp) > tolerance:
            errors.append(
                f"gwp_new + gwp_renewal ({split}) must be within ±1% of gwp ({record.gwp})"
            )

    # SPEC §5.7 — unknown broker needs a name to auto-register.
    if record.broker_id not in known_brokers and not record.broker_name:
        errors.append(
            f"unknown broker_id '{record.broker_id}' and no broker_name supplied "
            "for auto-registration"
        )
    return errors, warnings
