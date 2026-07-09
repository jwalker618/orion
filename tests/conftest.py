"""Shared fixtures: an isolated in-file SQLite DB per test session + TestClient."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Point the app at a throwaway DB before anything imports app.database.
_TEST_DB = Path(__file__).parent / "_test.db"
os.environ["ORION_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ORION_API_KEYS"] = "test-key,other-key"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.main import app, seed_reference_data  # noqa: E402
from app.models import Broker, BrokerSubmission, EntityPlan  # noqa: E402

HEADERS = {"X-API-Key": "test-key"}


def this_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


@pytest.fixture(scope="session")
def client():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    init_db()
    seed_reference_data()
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture()
def clean_db(client):
    """Truncate fact tables around a test that needs a pristine DB."""
    with SessionLocal() as db:
        db.query(BrokerSubmission).delete()
        db.query(EntityPlan).delete()
        db.query(Broker).delete()
        db.commit()
    yield client


def make_plan(**overrides) -> dict:
    record = {
        "entity_code": "MSRE",
        "coverage": "CYBER",
        "period": this_period(),
        "plan_gwp": "1000000.00",
        "plan_brokerage": "200000.00",
        "expected_hit_ratio": 0.35,
        "plan_loss_ratio": 0.55,
        "guardrail_low": "0.90",
        "guardrail_high": "1.20",
        "aggregate_limit": "50000000.00",
    }
    record.update(overrides)
    return record


def make_submission(**overrides) -> dict:
    record = {
        "entity_code": "MSRE",
        "broker_id": "BR-T001",
        "broker_name": "Test Broking",
        "broker_group": "Test Group",
        "tier": "GOLD",
        "coverage": "CYBER",
        "region": "UK",
        "period": this_period(),
        "quotes": 20,
        "binds": 8,
        "gwp": "400000.00",
        "gwp_new": "100000.00",
        "gwp_renewal": "300000.00",
        "brokerage": "80000.00",
        "total_limit": "5000000.00",
        "avg_premium_deviation": 1.05,
        "breach_count_amber": 1,
        "breach_count_red": 0,
        "incurred_loss_ratio": 0.5,
        "top_client_ref": "CL-1234",
        "top_client_limit": "2000000.00",
        "top_client_industry": "TECHNOLOGY",
    }
    record.update(overrides)
    return record
