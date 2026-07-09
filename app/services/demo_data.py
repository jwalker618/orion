"""Synthetic demo dataset (SPEC §6) — port of the HTML demo's generator.

5 entities, 8 coverages, 80 tiered brokers, 12 months, deterministic
(random seed 42). Correlations preserved: Platinum brokers bind at higher
hit ratios; guardrail breaches concentrate in CYBER and ENERGY; roughly 8%
of bound business sits in the amber+red bands.

Everything is produced as JSON-ready dicts shaped for the public POST
endpoints, so the same batches drive both `scripts/seed.py` (over HTTP) and
`POST /admin/reset` (through the same ingestion code path in-process).
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

SEED = 42

ENTITIES = [
    {"entity_code": "MSRE", "entity_name": "MS Reinsurance", "region": "Global"},
    {"entity_code": "AMLIN", "entity_name": "MS Amlin", "region": "UK"},
    {"entity_code": "MSEU", "entity_name": "MS Europe", "region": "Europe"},
    {"entity_code": "MSIJ", "entity_name": "Mitsui Sumitomo Insurance Japan", "region": "Japan"},
    {"entity_code": "MSIGUSA", "entity_name": "MSIG USA", "region": "North America"},
]

COVERAGES = [
    {"code": "PROPERTY", "description": "Property"},
    {"code": "CASUALTY", "description": "Casualty"},
    {"code": "MARINE", "description": "Marine"},
    {"code": "ENERGY", "description": "Energy"},
    {"code": "CYBER", "description": "Cyber"},
    {"code": "DO", "description": "Directors & Officers"},
    {"code": "PI", "description": "Professional Indemnity"},
    {"code": "FI", "description": "Financial Institutions"},
]

REGIONS = ["UK", "Europe", "North America", "Japan", "APAC", "LATAM", "Middle East"]

INDUSTRIES = [
    "MANUFACTURING", "FINANCIAL_SERVICES", "ENERGY", "TECHNOLOGY", "HEALTHCARE",
    "RETAIL", "TRANSPORT", "CONSTRUCTION", "REAL_ESTATE", "OTHER",
]

# tier -> (count, target hit ratio, quote volume scale)
TIER_PROFILE = {
    "PLATINUM": (10, 0.42, 40),
    "GOLD": (20, 0.35, 26),
    "SILVER": (30, 0.28, 16),
    "BRONZE": (20, 0.22, 9),
}

BROKER_GROUPS = [
    "Aegis Global", "Northgate", "Meridian Re", "Halcyon Partners", "Crescent",
    "Blackwood", "Stirling Risk", "Pacifica", "Atlas Broking", "Kestrel",
    "Windward", "Granite Bay", "Solstice", "Ironbridge", "Vantage Point",
]

NAME_A = [
    "Alden", "Barrow", "Caldwell", "Denholm", "Ellery", "Fairfax", "Garrick",
    "Halvers", "Ingram", "Jardine", "Kingsley", "Lonsdale", "Marchmont",
    "Norcroft", "Oakhurst", "Pemberton", "Quill", "Ravenswood", "Sablewood",
    "Thackeray",
]
NAME_B = ["Risk", "Insurance", "Broking", "Re", "Specialty", "Underwriting", "Partners", "Group"]

# coverage -> (avg premium per bind, loss-ratio mean, breach proneness).
# Proneness is the chance a broker/month row carries guardrail breaches at
# all; tuned so amber+red lands near 8% of bound business overall, heavily
# concentrated in CYBER and ENERGY (SPEC §6).
COVERAGE_PROFILE = {
    "PROPERTY": (95_000, 0.58, 0.15),
    "CASUALTY": (70_000, 0.62, 0.15),
    "MARINE": (55_000, 0.60, 0.15),
    "ENERGY": (160_000, 0.66, 0.45),
    "CYBER": (48_000, 0.52, 0.55),
    "DO": (42_000, 0.48, 0.12),
    "PI": (38_000, 0.50, 0.12),
    "FI": (60_000, 0.55, 0.15),
}


def current_period(today: datetime | None = None) -> str:
    now = today or datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


def last_n_periods(n: int, today: datetime | None = None) -> list[str]:
    now = today or datetime.now(timezone.utc)
    year, month = now.year, now.month
    periods: list[str] = []
    for _ in range(n):
        periods.append(f"{year}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(periods))


def generate_brokers(rng: random.Random) -> list[dict]:
    brokers: list[dict] = []
    idx = 0
    for tier, (count, _, _) in TIER_PROFILE.items():
        for _ in range(count):
            idx += 1
            name = f"{rng.choice(NAME_A)} {rng.choice(NAME_B)}"
            brokers.append(
                {
                    "broker_id": f"BR-{idx:04d}",
                    "broker_name": f"{name} ({idx:03d})",
                    "broker_group": rng.choice(BROKER_GROUPS) if rng.random() < 0.7 else None,
                    "tier": tier,
                    "home_region": rng.choice(REGIONS),
                    "is_new": rng.random() < 0.15,
                }
            )
    return brokers


def generate_dataset(today: datetime | None = None) -> dict:
    """Build the full synthetic set: brokers, plans and submissions."""
    rng = random.Random(SEED)
    periods = last_n_periods(12, today)
    brokers = generate_brokers(rng)

    # Each broker works one primary entity and a stable subset of coverages.
    assignments = []
    for b in brokers:
        entity = rng.choice(ENTITIES)["entity_code"]
        coverages = rng.sample([c["code"] for c in COVERAGES], k=rng.randint(2, 4))
        assignments.append((b, entity, coverages))

    submissions: list[dict] = []
    actual_gwp: dict[tuple[str, str, str], float] = {}
    for b, entity, coverages in assignments:
        tier = b["tier"]
        _, target_hr, quote_scale = TIER_PROFILE[tier]
        for coverage in coverages:
            avg_premium, lr_mean, breach_prone = COVERAGE_PROFILE[coverage]
            for period in periods:
                quotes = max(1, int(rng.gauss(quote_scale, quote_scale * 0.3)))
                hit = min(0.95, max(0.02, rng.gauss(target_hr, 0.06)))
                binds = min(quotes, int(round(quotes * hit)))
                gwp = round(binds * avg_premium * rng.uniform(0.7, 1.3), 2)
                new_share = 0.6 if b["is_new"] else rng.uniform(0.15, 0.35)
                gwp_new = round(gwp * new_share, 2)
                gwp_renewal = round(gwp - gwp_new, 2)
                deviation = max(
                    0.6, rng.gauss(1.02, 0.10 if breach_prone > 0.3 else 0.05)
                )
                amber = red = 0
                if binds and rng.random() < breach_prone:
                    amber = rng.randint(1, max(1, binds // 2))
                    if rng.random() < 0.4:
                        red = rng.randint(1, max(1, binds // 4))
                record = {
                    "entity_code": entity,
                    "broker_id": b["broker_id"],
                    "broker_name": b["broker_name"],
                    "broker_group": b["broker_group"],
                    "tier": tier,
                    "coverage": coverage,
                    "region": b["home_region"],
                    "period": period,
                    "currency": "USD",
                    "quotes": quotes,
                    "binds": binds,
                    "gwp": str(gwp),
                    "gwp_new": str(gwp_new),
                    "gwp_renewal": str(gwp_renewal),
                    "brokerage": str(round(gwp * rng.uniform(0.15, 0.25), 2)),
                    "total_limit": str(round(gwp * rng.uniform(8, 25), 2)),
                    "avg_premium_deviation": round(deviation, 4),
                    "breach_count_amber": amber,
                    "breach_count_red": red,
                }
                if rng.random() < 0.6:
                    record["incurred_loss_ratio"] = round(
                        max(0.0, rng.gauss(lr_mean, 0.18)), 4
                    )
                if rng.random() < 0.3:
                    record["top_client_ref"] = f"CL-{rng.randint(1000, 9999)}"
                    record["top_client_limit"] = str(
                        round(float(record["total_limit"]) * rng.uniform(0.1, 0.4), 2)
                    )
                    record["top_client_industry"] = rng.choice(INDUSTRIES)
                submissions.append(record)
                key = (entity, coverage, period)
                actual_gwp[key] = actual_gwp.get(key, 0.0) + gwp

    plans: list[dict] = []
    for entity in (e["entity_code"] for e in ENTITIES):
        for coverage in (c["code"] for c in COVERAGES):
            _, lr_mean, breach_prone = COVERAGE_PROFILE[coverage]
            for period in periods:
                actual = actual_gwp.get((entity, coverage, period), 0.0)
                # Plan around the realised number so plan-vs-actual variance
                # is meaningful but not absurd; keep a plan even where no
                # broker wrote business (attainment 0 shows up honestly).
                plan_gwp = actual * rng.uniform(0.9, 1.2) if actual else rng.uniform(1e5, 8e5)
                plans.append(
                    {
                        "entity_code": entity,
                        "coverage": coverage,
                        "period": period,
                        "currency": "USD",
                        "plan_gwp": str(round(plan_gwp, 2)),
                        "plan_brokerage": str(round(plan_gwp * 0.2, 2)),
                        "expected_hit_ratio": round(rng.uniform(0.26, 0.40), 4),
                        "expected_bind_count": rng.randint(20, 200),
                        "plan_loss_ratio": round(max(0.2, rng.gauss(lr_mean, 0.05)), 4),
                        "guardrail_low": "0.90",
                        "guardrail_high": "1.20",
                        "aggregate_limit": str(
                            round(plan_gwp * (4 if breach_prone > 0.3 else 40), 2)
                        ),
                    }
                )

    return {"brokers": brokers, "plans": plans, "submissions": submissions}


def batched(records: list[dict], size: int) -> list[list[dict]]:
    return [records[i : i + size] for i in range(0, len(records), size)]
