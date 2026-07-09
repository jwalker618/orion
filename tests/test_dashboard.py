"""Dashboard GETs against a small hand-computed fixture (SPEC §7)."""

from __future__ import annotations

import pytest

from app.services.aggregation import prev_period
from tests.conftest import HEADERS, make_plan, make_submission, this_period

CUR = this_period()
PREV = prev_period(CUR)


@pytest.fixture()
def seeded(clean_db):
    """Two brokers (one group), two coverages, two months — all hand-checkable."""
    client = clean_db
    plans = [
        make_plan(period=CUR, plan_gwp="1000000.00", expected_hit_ratio=0.5,
                  plan_loss_ratio=0.5, aggregate_limit="3000000.00"),
        make_plan(period=PREV, plan_gwp="1000000.00", expected_hit_ratio=0.5,
                  plan_loss_ratio=0.5, aggregate_limit="3000000.00"),
        make_plan(period=CUR, coverage="PROPERTY", plan_gwp="500000.00",
                  expected_hit_ratio=0.3, plan_loss_ratio=0.6),
    ]
    report = client.post("/api/v1/entity-plans", json={"records": plans}, headers=HEADERS).json()
    assert report["accepted"] == 3

    subs = [
        make_submission(  # BR-A, CYBER, current month — breaching, lossy
            broker_id="BR-A", broker_name="Alpha Broking", broker_group="G1",
            tier="PLATINUM", period=CUR, quotes=10, binds=5,
            gwp="600000.00", gwp_new="300000.00", gwp_renewal="300000.00",
            brokerage="120000.00", total_limit="2000000.00",
            avg_premium_deviation=1.25, breach_count_amber=1, breach_count_red=1,
            incurred_loss_ratio=0.8, top_client_ref="CL-0001",
            top_client_limit="2000000.00", top_client_industry="TECHNOLOGY",
        ),
        make_submission(  # BR-B, CYBER, current month — clean
            broker_id="BR-B", broker_name="Beta Broking", broker_group="G1",
            tier="GOLD", period=CUR, quotes=10, binds=2,
            gwp="200000.00", gwp_new="50000.00", gwp_renewal="150000.00",
            brokerage="40000.00", total_limit="1500000.00",
            avg_premium_deviation=0.95, breach_count_amber=0, breach_count_red=0,
            incurred_loss_ratio=None, top_client_ref="CL-0002",
            top_client_limit="1500000.00", top_client_industry="RETAIL",
        ),
        make_submission(  # BR-A, CYBER, previous month
            broker_id="BR-A", broker_name="Alpha Broking", broker_group="G1",
            tier="PLATINUM", period=PREV, quotes=10, binds=4,
            gwp="500000.00", gwp_new="250000.00", gwp_renewal="250000.00",
            brokerage="100000.00", total_limit="1800000.00",
            avg_premium_deviation=1.0, breach_count_amber=0, breach_count_red=0,
            incurred_loss_ratio=None, top_client_ref=None,
            top_client_limit=None, top_client_industry=None,
        ),
        make_submission(  # BR-B, PROPERTY, current month (for coverage filters)
            broker_id="BR-B", broker_name="Beta Broking", broker_group="G1",
            tier="GOLD", coverage="PROPERTY", region="Europe", period=CUR,
            quotes=20, binds=6, gwp="300000.00", gwp_new="100000.00",
            gwp_renewal="200000.00", brokerage="60000.00", total_limit="900000.00",
            avg_premium_deviation=1.02, breach_count_amber=0, breach_count_red=0,
            incurred_loss_ratio=None, top_client_ref=None,
            top_client_limit=None, top_client_industry=None,
        ),
    ]
    report = client.post(
        "/api/v1/broker-submissions", json={"records": subs}, headers=HEADERS
    ).json()
    assert report["accepted"] == 4 and not report["rejected"]
    return client


class TestExecutive:
    def test_kpis_and_series(self, seeded):
        body = seeded.get("/api/v1/dashboard/executive", headers=HEADERS).json()
        assert body["as_of"] and body["filters"] == {"limit": 100, "offset": 0}

        # binds 5+2+4+6 = 17, quotes 10+10+10+20 = 50
        assert body["kpis"]["hit_ratio"]["value"] == pytest.approx(17 / 50)
        # breaches (1+1) over 17 binds
        assert body["kpis"]["breach_pct"]["value"] == pytest.approx(2 / 17)
        # gwp 1.6M vs plan 2.5M
        assert body["kpis"]["plan_attainment_gwp"]["value"] == pytest.approx(1.6 / 2.5)
        assert body["kpis"]["total_exposure"]["value"] == "6200000.00"

        assert len(body["series"]) == 12
        latest = body["series"][-1]
        assert latest["period"] == CUR
        assert latest["hit_ratio"] == pytest.approx(13 / 40)
        assert latest["gwp"] == "1100000.00"

        # MoM: hit ratio 0.325 this month vs 0.4 last month
        assert body["kpis"]["hit_ratio"]["mom_trend"] == pytest.approx(
            (13 / 40 - 4 / 10) / (4 / 10)
        )

    def test_top_brokers_and_alerts(self, seeded):
        body = seeded.get("/api/v1/dashboard/executive", headers=HEADERS).json()
        assert body["top_brokers"][0]["broker_id"] == "BR-A"  # 1.1M beats 0.5M
        assert body["top_brokers"][0]["gwp"] == "1100000.00"

        types = {a["type"] for a in body["alerts"]}
        assert "guardrail_breach" in types  # BR-A red breach
        assert "aggregate_limit_breach" in types  # 3.5M client limits > 3.0M cap
        assert "hit_ratio_below_plan" in types  # 0.35 < 0.5 plan
        red = [a for a in body["alerts"] if a["type"] == "guardrail_breach"][0]
        assert red["severity"] == "red"


class TestBrokers:
    def test_leaderboard(self, seeded):
        body = seeded.get("/api/v1/brokers", headers=HEADERS).json()
        assert body["total"] == 2
        first = body["rows"][0]
        assert first["broker_id"] == "BR-A"
        assert first["broker_group"] == "G1"
        assert first["tier"] == "PLATINUM"
        assert first["hit_ratio"] == pytest.approx(9 / 20)
        assert first["brokerage"] == "220000.00"
        assert len(first["sparkline"]) == 12
        assert first["sparkline"][-1] == pytest.approx(600000.0)
        assert first["sparkline"][-2] == pytest.approx(500000.0)
        # deviation weighted by binds: (1.25*5 + 1.0*4) / 9
        assert first["avg_premium_deviation"] == pytest.approx((1.25 * 5 + 1.0 * 4) / 9)

    def test_tier_filter(self, seeded):
        body = seeded.get("/api/v1/brokers?tier=GOLD", headers=HEADERS).json()
        assert [r["broker_id"] for r in body["rows"]] == ["BR-B"]

    def test_profile_share_of_wallet(self, seeded):
        body = seeded.get("/api/v1/brokers/BR-A", headers=HEADERS).json()
        assert body["share_of_wallet"] == pytest.approx(1_100_000 / 1_600_000)
        assert len(body["monthly"]) == 12
        assert body["monthly"][-1]["binds"] == 5
        assert [c["coverage"] for c in body["coverages"]] == ["CYBER"]

    def test_profile_404(self, seeded):
        assert seeded.get("/api/v1/brokers/BR-NOPE", headers=HEADERS).status_code == 404


class TestExposure:
    def test_aggregates_and_lorenz(self, seeded):
        body = seeded.get("/api/v1/dashboard/exposure", headers=HEADERS).json()
        regions = {r["name"]: r for r in body["by_region"]}
        assert regions["UK"]["total_limit"] == "5300000.00"
        assert regions["Europe"]["total_limit"] == "900000.00"
        coverages = {c["name"]: c for c in body["by_coverage"]}
        assert coverages["CYBER"]["gwp"] == "1300000.00"

        assert [c["client_ref"] for c in body["top_clients"]] == ["CL-0001", "CL-0002"]
        # Lorenz over limits [1.5M, 2.0M]: (0.5, 1.5/3.5), (1.0, 1.0)
        assert body["lorenz"][-1] == {"x": 1.0, "y": 1.0}
        assert body["lorenz"][1]["y"] == pytest.approx(1.5 / 3.5)
        assert any(a["type"] == "aggregate_limit_breach" for a in body["alerts"])

    def test_filters_actually_filter(self, seeded):
        body = seeded.get(
            "/api/v1/dashboard/exposure?coverage=PROPERTY", headers=HEADERS
        ).json()
        assert body["filters"]["coverage"] == "PROPERTY"
        assert [c["name"] for c in body["by_coverage"]] == ["PROPERTY"]
        assert body["top_clients"] == []


class TestGuardrails:
    def test_histogram_and_breach_list(self, seeded):
        body = seeded.get("/api/v1/dashboard/guardrails", headers=HEADERS).json()
        assert sum(b["count"] for b in body["histogram"]) == 17  # weighted by binds
        by_cov = {c["coverage"]: c for c in body["by_coverage"]}
        assert by_cov["CYBER"]["amber"] == 1 and by_cov["CYBER"]["red"] == 1
        assert by_cov["CYBER"]["breach_pct"] == pytest.approx(2 / 11)
        assert len(body["breach_list"]) == 1
        row = body["breach_list"][0]
        assert row["broker_id"] == "BR-A"
        assert row["guardrail_high"] == pytest.approx(1.2)
        assert body["what_if"] is None

    def test_what_if_threshold_is_monotone(self, seeded):
        def breached(threshold: float) -> int:
            body = seeded.get(
                f"/api/v1/dashboard/guardrails?threshold={threshold}", headers=HEADERS
            ).json()
            assert body["what_if"]["threshold"] == threshold
            return body["what_if"]["breached_binds"]

        # deviations: 1.25 (5 binds), 0.95 (2), 1.0 (4), 1.02 (6)
        assert breached(1.30) == 0
        assert breached(1.20) == 5
        assert breached(1.01) == 11
        counts = [breached(t) for t in (1.01, 1.20, 1.30)]
        assert counts == sorted(counts, reverse=True)


class TestPlanVsActual:
    def test_variances_and_flags(self, seeded):
        body = seeded.get("/api/v1/dashboard/plan-vs-actual", headers=HEADERS).json()
        rows = {r["coverage"]: r for r in body["rows"]}
        cyber = rows["CYBER"]
        assert cyber["plan_gwp"] == "2000000.00"
        assert cyber["actual_gwp"] == "1300000.00"
        assert cyber["plan_attainment_gwp"] == pytest.approx(0.65)
        assert cyber["hit_ratio"] == pytest.approx(11 / 30)
        assert cyber["hit_ratio_variance"] == pytest.approx(11 / 30 - 0.5)
        assert cyber["incurred_loss_ratio"] == pytest.approx(0.8)  # only BR-A reported one
        assert cyber["loss_ratio_variance"] == pytest.approx(0.3)
        assert set(cyber["flags"]) == {
            "GWP_BELOW_PLAN", "HIT_RATIO_BELOW_PLAN", "LOSS_RATIO_ABOVE_PLAN",
        }

    def test_entity_filter(self, seeded):
        body = seeded.get(
            "/api/v1/dashboard/plan-vs-actual?entity=MSIJ", headers=HEADERS
        ).json()
        assert body["rows"] == []


class TestBrowse:
    def test_paginated_plans(self, seeded):
        body = seeded.get("/api/v1/entity-plans?limit=2", headers=HEADERS).json()
        assert body["total"] == 3
        assert len(body["records"]) == 2
        page2 = seeded.get("/api/v1/entity-plans?limit=2&offset=2", headers=HEADERS).json()
        assert len(page2["records"]) == 1
        assert page2["records"][0]["plan_gwp"].endswith(".00")  # decimal string

    def test_period_filter(self, seeded):
        body = seeded.get(
            f"/api/v1/broker-submissions?period_from={CUR}&period_to={CUR}",
            headers=HEADERS,
        ).json()
        assert body["total"] == 3
        assert all(r["period"] == CUR for r in body["records"])

    def test_bad_period_filter_is_422(self, seeded):
        response = seeded.get("/api/v1/entity-plans?period_from=nope", headers=HEADERS)
        assert response.status_code == 422
        assert response.json()["title"]

    def test_dashboard_needs_auth(self, seeded):
        assert seeded.get("/api/v1/dashboard/executive").status_code == 401


class TestAdmin:
    def test_health_counts(self, seeded):
        body = seeded.get("/api/v1/health").json()
        assert body == {
            "status": "ok", "db": "ok", "records": {"plans": 3, "submissions": 4},
        }

    def test_reset_and_reseed(self, seeded):
        body = seeded.post("/api/v1/admin/reset?reseed=true", headers=HEADERS).json()
        assert body["status"] == "reset" and body["reseeded"] is True
        assert body["report"]["rejected"] == {"plans": 0, "submissions": 0}
        assert body["report"]["accepted"]["plans"] == 480  # 5 entities × 8 coverages × 12 months
        assert body["report"]["accepted"]["submissions"] > 1000

        health = seeded.get("/api/v1/health").json()
        assert health["records"]["plans"] == 480

        # Reset without reseed empties the facts again.
        seeded.post("/api/v1/admin/reset", headers=HEADERS)
        health = seeded.get("/api/v1/health").json()
        assert health["records"] == {"plans": 0, "submissions": 0}
