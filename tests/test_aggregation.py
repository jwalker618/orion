"""Hand-computed fixtures for every derived metric (SPEC §3.4, §7)."""

from __future__ import annotations

import pytest

from app.services import aggregation as agg


class TestRatios:
    def test_hit_ratio(self):
        assert agg.hit_ratio(30, 100) == pytest.approx(0.3)

    def test_hit_ratio_div_zero_is_none(self):
        assert agg.hit_ratio(0, 0) is None
        assert agg.hit_ratio(None, 10) is None

    def test_plan_attainment(self):
        assert agg.plan_attainment(110, 100) == pytest.approx(1.1)
        assert agg.plan_attainment(50, 0) is None

    def test_variance(self):
        assert agg.variance(0.30, 0.35) == pytest.approx(-0.05)
        assert agg.variance(None, 0.35) is None
        assert agg.variance(0.30, None) is None

    def test_breach_pct(self):
        assert agg.breach_pct(3, 1, 50) == pytest.approx(0.08)
        assert agg.breach_pct(3, 1, 0) is None

    def test_share_of_wallet(self):
        assert agg.share_of_wallet(25, 100) == pytest.approx(0.25)
        assert agg.share_of_wallet(25, 0) is None

    def test_mom_trend(self):
        assert agg.mom_trend(110, 100) == pytest.approx(0.10)
        assert agg.mom_trend(90, 100) == pytest.approx(-0.10)
        assert agg.mom_trend(100, 0) is None
        assert agg.mom_trend(None, 100) is None

    def test_weighted_avg(self):
        assert agg.weighted_avg([(1.0, 1), (2.0, 3)]) == pytest.approx(1.75)
        assert agg.weighted_avg([]) is None
        # zero total weight falls back to a simple mean
        assert agg.weighted_avg([(1.0, 0), (3.0, 0)]) == pytest.approx(2.0)


class TestPeriods:
    def test_prev_period(self):
        assert agg.prev_period("2026-07") == "2026-06"
        assert agg.prev_period("2026-01") == "2025-12"

    def test_month_sequence(self):
        assert agg.month_sequence("2026-02", 4) == ["2025-11", "2025-12", "2026-01", "2026-02"]


class TestLorenz:
    def test_empty(self):
        assert agg.lorenz_points([]) == [{"x": 0.0, "y": 0.0}]

    def test_perfect_equality_is_diagonal(self):
        points = agg.lorenz_points([10, 10, 10, 10])
        for p in points:
            assert p["y"] == pytest.approx(p["x"])

    def test_hand_computed_curve(self):
        # limits 1, 1, 2, 6 → total 10; cumulative shares 0.1, 0.2, 0.4, 1.0
        points = agg.lorenz_points([6, 1, 2, 1])
        assert [round(p["x"], 2) for p in points] == [0.0, 0.25, 0.5, 0.75, 1.0]
        assert [round(p["y"], 2) for p in points] == [0.0, 0.1, 0.2, 0.4, 1.0]

    def test_gini(self):
        assert agg.gini([10, 10, 10]) == pytest.approx(0.0)
        assert agg.gini([]) is None
        # All wealth with one holder of n=4 → gini = (n-1)/n = 0.75
        assert agg.gini([0, 0, 0, 100]) == pytest.approx(0.75)


class TestHistogram:
    def test_buckets_and_weights(self):
        buckets = agg.deviation_histogram(
            [(0.5, 2), (0.92, 3), (1.02, 5), (1.5, 1)],
            edges=[0.90, 1.00, 1.20],
        )
        assert [b["label"] for b in buckets] == ["<0.90", "0.90–1.00", "1.00–1.20", "≥1.20"]
        assert [b["count"] for b in buckets] == [2, 3, 5, 1]

    def test_edge_values_fall_in_upper_bucket(self):
        buckets = agg.deviation_histogram([(0.90, 1)], edges=[0.90, 1.00])
        assert buckets[1]["count"] == 1


class TestWhatIf:
    ROWS = [(0.85, 10), (0.95, 10), (1.10, 10), (1.30, 10)]

    def test_hand_computed(self):
        result = agg.what_if_breaches(self.ROWS, threshold=1.20)
        # 0.85 (below band) and 1.30 (above threshold) breach.
        assert result == {"breached_rows": 2, "breached_binds": 20}

    def test_threshold_is_monotone(self):
        counts = [
            agg.what_if_breaches(self.ROWS, threshold=t)["breached_rows"]
            for t in (1.05, 1.15, 1.25, 1.35)
        ]
        assert counts == sorted(counts, reverse=True)
