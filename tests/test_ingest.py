"""Ingestion coverage (SPEC §7): happy path, each validation rule, partial
batches, idempotent re-POST, upsert-overwrites, auth."""

from __future__ import annotations

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Broker, EntityPlan
from tests.conftest import HEADERS, make_plan, make_submission, this_period

PLANS = "/api/v1/entity-plans"
SUBMISSIONS = "/api/v1/broker-submissions"
BROKERS = "/api/v1/reference/brokers"


class TestAuth:
    def test_missing_key_is_401(self, client):
        response = client.post(PLANS, json={"records": [make_plan()]})
        assert response.status_code == 401

    def test_wrong_key_is_401(self, client):
        response = client.post(
            PLANS, json={"records": [make_plan()]}, headers={"X-API-Key": "nope"}
        )
        assert response.status_code == 401
        assert response.json()["title"]

    def test_health_is_open(self, client):
        assert client.get("/api/v1/health").status_code == 200


class TestEntityPlans:
    def test_happy_path_then_idempotent_repost(self, clean_db):
        client = clean_db
        batch = {"records": [make_plan(), make_plan(coverage="ENERGY")]}
        first = client.post(PLANS, json=batch, headers=HEADERS).json()
        assert (first["accepted"], first["updated"], first["rejected"]) == (2, 0, [])

        again = client.post(PLANS, json=batch, headers=HEADERS).json()
        assert (again["accepted"], again["updated"]) == (0, 2)

        with SessionLocal() as db:
            assert db.scalar(select(EntityPlan).where(EntityPlan.coverage == "CYBER"))

    def test_upsert_overwrites(self, clean_db):
        client = clean_db
        client.post(PLANS, json={"records": [make_plan(plan_gwp="100.00")]}, headers=HEADERS)
        client.post(PLANS, json={"records": [make_plan(plan_gwp="999.00")]}, headers=HEADERS)
        with SessionLocal() as db:
            rows = list(db.scalars(select(EntityPlan)))
        assert len(rows) == 1
        assert str(rows[0].plan_gwp) == "999.00"

    def test_unknown_entity_rejected(self, clean_db):
        report = clean_db.post(
            PLANS, json={"records": [make_plan(entity_code="NOPE")]}, headers=HEADERS
        ).json()
        assert report["accepted"] == 0
        assert "unknown entity_code" in report["rejected"][0]["errors"][0]

    def test_unknown_coverage_rejected(self, clean_db):
        report = clean_db.post(
            PLANS, json={"records": [make_plan(coverage="ALIEN")]}, headers=HEADERS
        ).json()
        assert report["accepted"] == 0
        assert any("coverage" in e for e in report["rejected"][0]["errors"])

    def test_future_period_rejected(self, clean_db):
        report = clean_db.post(
            PLANS, json={"records": [make_plan(period="2999-01")]}, headers=HEADERS
        ).json()
        assert report["accepted"] == 0
        assert any("future" in e for e in report["rejected"][0]["errors"])

    def test_bad_period_format_rejected(self, clean_db):
        report = clean_db.post(
            PLANS, json={"records": [make_plan(period="2026-13")]}, headers=HEADERS
        ).json()
        assert report["accepted"] == 0

    def test_guardrail_order_rejected(self, clean_db):
        report = clean_db.post(
            PLANS,
            json={"records": [make_plan(guardrail_low="1.30", guardrail_high="1.10")]},
            headers=HEADERS,
        ).json()
        assert report["accepted"] == 0

    def test_guardrail_sanity_warning_accepted(self, clean_db):
        report = clean_db.post(
            PLANS,
            json={"records": [make_plan(guardrail_low="1.01", guardrail_high="1.20")]},
            headers=HEADERS,
        ).json()
        assert report["accepted"] == 1
        assert report["warnings"]

    def test_partial_batch(self, clean_db):
        batch = {
            "records": [
                make_plan(),
                make_plan(entity_code="NOPE", coverage="ENERGY"),
                make_plan(coverage="MARINE", expected_hit_ratio=7),
            ]
        }
        report = clean_db.post(PLANS, json=batch, headers=HEADERS).json()
        assert report["accepted"] == 1
        assert {r["index"] for r in report["rejected"]} == {1, 2}
        # Field-level Pydantic errors are itemised.
        assert any("expected_hit_ratio" in e for e in report["rejected"][1]["errors"])

    def test_extra_field_rejected(self, clean_db):
        report = clean_db.post(
            PLANS, json={"records": [make_plan(surprise=1)]}, headers=HEADERS
        ).json()
        assert report["accepted"] == 0


class TestBrokerSubmissions:
    def test_happy_path_auto_registers_broker(self, clean_db):
        client = clean_db
        report = client.post(
            SUBMISSIONS, json={"records": [make_submission()]}, headers=HEADERS
        ).json()
        assert (report["accepted"], report["rejected"]) == (1, [])
        with SessionLocal() as db:
            broker = db.get(Broker, "BR-T001")
        assert broker is not None
        assert broker.broker_name == "Test Broking"
        assert broker.tier == "GOLD"

    def test_idempotent_repost_and_overwrite(self, clean_db):
        client = clean_db
        client.post(SUBMISSIONS, json={"records": [make_submission()]}, headers=HEADERS)
        report = client.post(
            SUBMISSIONS,
            json={"records": [make_submission(quotes=30, binds=9, gwp="500000.00",
                                               gwp_new=None, gwp_renewal=None)]},
            headers=HEADERS,
        ).json()
        assert (report["accepted"], report["updated"]) == (0, 1)
        browse = client.get(SUBMISSIONS, headers=HEADERS).json()
        assert browse["total"] == 1
        assert browse["records"][0]["quotes"] == 30

    def test_binds_gt_quotes_rejected(self, clean_db):
        report = clean_db.post(
            SUBMISSIONS,
            json={"records": [make_submission(binds=25, quotes=20)]},
            headers=HEADERS,
        ).json()
        assert "must be <= quotes" in report["rejected"][0]["errors"][0]

    def test_gwp_split_tolerance(self, clean_db):
        bad = make_submission(gwp="400000.00", gwp_new="300000.00", gwp_renewal="300000.00")
        report = clean_db.post(SUBMISSIONS, json={"records": [bad]}, headers=HEADERS).json()
        assert any("±1%" in e for e in report["rejected"][0]["errors"])

        ok = make_submission(gwp="400000.00", gwp_new="199000.00", gwp_renewal="203000.00")
        report = clean_db.post(SUBMISSIONS, json={"records": [ok]}, headers=HEADERS).json()
        assert report["accepted"] == 1

    def test_unknown_broker_without_name_rejected(self, clean_db):
        record = make_submission(broker_id="BR-GHOST", broker_name=None)
        report = clean_db.post(SUBMISSIONS, json={"records": [record]}, headers=HEADERS).json()
        assert any("auto-registration" in e for e in report["rejected"][0]["errors"])

    def test_privacy_guard_rejects_pii_like_refs(self, clean_db):
        for bad_ref in ("jane.doe@example.com", "+44 7700 900123", "John Smith"):
            report = clean_db.post(
                SUBMISSIONS,
                json={"records": [make_submission(top_client_ref=bad_ref)]},
                headers=HEADERS,
            ).json()
            assert report["accepted"] == 0, bad_ref
            assert any("anonymised" in e for e in report["rejected"][0]["errors"])

    def test_unknown_entity_rejected(self, clean_db):
        report = clean_db.post(
            SUBMISSIONS,
            json={"records": [make_submission(entity_code="NOPE")]},
            headers=HEADERS,
        ).json()
        assert report["accepted"] == 0


class TestBrokerRegistry:
    def test_bulk_upsert(self, clean_db):
        client = clean_db
        records = [
            {"broker_id": "BR-X1", "broker_name": "X One", "tier": "PLATINUM"},
            {"broker_id": "BR-X2", "broker_name": "X Two"},
        ]
        report = client.post(BROKERS, json={"records": records}, headers=HEADERS).json()
        assert report["accepted"] == 2

        records[0]["broker_name"] = "X One Renamed"
        report = client.post(BROKERS, json={"records": records}, headers=HEADERS).json()
        assert report["updated"] == 2
        with SessionLocal() as db:
            assert db.get(Broker, "BR-X1").broker_name == "X One Renamed"


def test_submission_period_can_be_next_month(clean_db):
    period = this_period()
    year, month = int(period[:4]), int(period[5:])
    nxt = f"{year + 1}-01" if month == 12 else f"{year}-{month + 1:02d}"
    report = clean_db.post(
        SUBMISSIONS, json={"records": [make_submission(period=nxt)]}, headers=HEADERS
    ).json()
    assert report["accepted"] == 1
    # ...but two months out is rejected
    year2, month2 = int(nxt[:4]), int(nxt[5:])
    nxt2 = f"{year2 + 1}-01" if month2 == 12 else f"{year2}-{month2 + 1:02d}"
    report = clean_db.post(
        SUBMISSIONS, json={"records": [make_submission(period=nxt2)]}, headers=HEADERS
    ).json()
    assert report["accepted"] == 0
