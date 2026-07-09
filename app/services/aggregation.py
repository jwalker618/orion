"""All derived-metric math (SPEC §3.4). Pure functions, unit-tested.

Nothing in here touches the database or FastAPI: routers gather rows and hand
plain numbers in. Every ratio guards division-by-zero by returning None.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

Number = int | float | Decimal


def safe_ratio(numerator: Number | None, denominator: Number | None) -> float | None:
    """num / den with div-zero (and missing operand) guarded to None."""
    if numerator is None or denominator is None or float(denominator) == 0.0:
        return None
    return float(numerator) / float(denominator)


def hit_ratio(binds: Number | None, quotes: Number | None) -> float | None:
    """Σbinds / Σquotes."""
    return safe_ratio(binds, quotes)


def plan_attainment(actual_gwp: Number | None, plan_gwp: Number | None) -> float | None:
    """Σgwp / Σplan_gwp."""
    return safe_ratio(actual_gwp, plan_gwp)


def variance(actual: Number | None, expected: Number | None) -> float | None:
    """actual − expected, None if either side is unknown."""
    if actual is None or expected is None:
        return None
    return float(actual) - float(expected)


def breach_pct(amber: Number, red: Number, binds: Number | None) -> float | None:
    """(amber + red) / binds."""
    return safe_ratio(float(amber) + float(red), binds)


def share_of_wallet(broker_gwp: Number | None, group_gwp: Number | None) -> float | None:
    """Broker GWP ÷ broker-group total GWP (DP-03 precursor)."""
    return safe_ratio(broker_gwp, group_gwp)


def mom_trend(current: Number | None, previous: Number | None) -> float | None:
    """Relative month-on-month change: (current − previous) / previous."""
    if current is None or previous is None or float(previous) == 0.0:
        return None
    return (float(current) - float(previous)) / float(previous)


def weighted_avg(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Weighted mean of (value, weight) pairs; simple mean if weights sum to 0."""
    if not pairs:
        return None
    total_weight = sum(w for _, w in pairs)
    if total_weight == 0.0:
        return sum(v for v, _ in pairs) / len(pairs)
    return sum(v * w for v, w in pairs) / total_weight


# --- periods ---------------------------------------------------------------


def prev_period(period: str) -> str:
    """The month before an ISO YYYY-MM period."""
    year, month = int(period[:4]), int(period[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def month_sequence(end_period: str, n: int) -> list[str]:
    """The n ISO months ending at (and including) end_period, ascending."""
    months: list[str] = [end_period]
    for _ in range(n - 1):
        months.append(prev_period(months[-1]))
    return list(reversed(months))


# --- distributions ----------------------------------------------------------


def lorenz_points(values: Sequence[Number]) -> list[dict[str, float]]:
    """Lorenz curve over client limits (SPEC §3.4 concentration).

    Returns points {x, y} where x is the cumulative share of clients (smallest
    limit first) and y the cumulative share of total limit. Always anchored at
    (0, 0); empty input yields just the anchor.
    """
    points = [{"x": 0.0, "y": 0.0}]
    cleaned = sorted(float(v) for v in values)
    total = sum(cleaned)
    if not cleaned or total == 0.0:
        return points
    running = 0.0
    count = len(cleaned)
    for i, v in enumerate(cleaned, start=1):
        running += v
        points.append({"x": i / count, "y": running / total})
    return points


def gini(values: Sequence[Number]) -> float | None:
    """Gini coefficient from the same distribution the Lorenz curve shows."""
    cleaned = sorted(float(v) for v in values)
    n = len(cleaned)
    total = sum(cleaned)
    if n == 0 or total == 0.0:
        return None
    # Standard formula over sorted values.
    weighted = sum((i + 1) * v for i, v in enumerate(cleaned))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


DEFAULT_DEVIATION_EDGES = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20, 1.30]


def deviation_histogram(
    deviations: Sequence[tuple[float, int]],
    edges: Sequence[float] = DEFAULT_DEVIATION_EDGES,
) -> list[dict]:
    """Bucket (avg_premium_deviation, weight) pairs into labelled bands.

    Buckets are (-inf, e0), [e0, e1), …, [eN, +inf). Weight is typically the
    bind count so the histogram reflects volume, not submission-row count.
    """
    bounds = list(edges)
    buckets = [
        {"low": None, "high": bounds[0], "label": f"<{bounds[0]:.2f}", "count": 0},
    ]
    for lo, hi in zip(bounds, bounds[1:]):
        buckets.append({"low": lo, "high": hi, "label": f"{lo:.2f}–{hi:.2f}", "count": 0})
    buckets.append({"low": bounds[-1], "high": None, "label": f"≥{bounds[-1]:.2f}", "count": 0})

    for deviation, weight in deviations:
        placed = False
        for bucket in buckets:
            low_ok = bucket["low"] is None or deviation >= bucket["low"]
            high_ok = bucket["high"] is None or deviation < bucket["high"]
            if low_ok and high_ok:
                bucket["count"] += weight
                placed = True
                break
        if not placed:  # pragma: no cover — bands are exhaustive
            buckets[-1]["count"] += weight
    return buckets


def what_if_breaches(
    rows: Sequence[tuple[float, int]],
    threshold: float,
    lower_band: float = 0.90,
) -> dict[str, int]:
    """Recompute breach counts under a hypothetical upper band (SPEC §4.2).

    A row (avg_premium_deviation, binds) breaches when its deviation falls
    outside [lower_band, threshold]. Raising the threshold can only reduce or
    hold the breach count — monotone by construction.
    """
    breached_rows = 0
    breached_binds = 0
    for deviation, binds in rows:
        if deviation > threshold or deviation < lower_band:
            breached_rows += 1
            breached_binds += binds
    return {"breached_rows": breached_rows, "breached_binds": breached_binds}
