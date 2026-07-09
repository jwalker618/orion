"""Dashboard read model (SPEC §4.2): aggregate GETs per demo tab + raw browse.

Routers only gather rows and assemble responses — every derived number comes
from app.services.aggregation. Demo-scale data (thousands of rows) is
aggregated in Python; the Postgres upgrade path would push these GROUP BYs
into SQL without changing the response contracts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthDep, FiltersDep, ListFilters
from app.models import Broker, BrokerSubmission, Entity, EntityPlan
from app.schemas import dashboard as ds
from app.schemas.plans import EntityPlanOut
from app.schemas.submissions import BrokerSubmissionOut
from app.services import aggregation as agg

router = APIRouter(tags=["dashboard"], dependencies=[AuthDep])

ZERO = Decimal("0")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- row gathering -----------------------------------------------------------


def _submission_rows(db: Session, f: ListFilters) -> list[BrokerSubmission]:
    stmt = select(BrokerSubmission)
    if f.tier:
        stmt = stmt.join(Broker, Broker.broker_id == BrokerSubmission.broker_id).where(
            Broker.tier == f.tier
        )
    if f.entity:
        stmt = stmt.where(BrokerSubmission.entity_code == f.entity)
    if f.coverage:
        stmt = stmt.where(BrokerSubmission.coverage == f.coverage)
    if f.region:
        stmt = stmt.where(BrokerSubmission.region == f.region)
    if f.period_from:
        stmt = stmt.where(BrokerSubmission.period >= f.period_from)
    if f.period_to:
        stmt = stmt.where(BrokerSubmission.period <= f.period_to)
    return list(db.scalars(stmt))


def _plan_rows(db: Session, f: ListFilters) -> list[EntityPlan]:
    stmt = select(EntityPlan)
    if f.entity:
        stmt = stmt.where(EntityPlan.entity_code == f.entity)
    if f.coverage:
        stmt = stmt.where(EntityPlan.coverage == f.coverage)
    if f.period_from:
        stmt = stmt.where(EntityPlan.period >= f.period_from)
    if f.period_to:
        stmt = stmt.where(EntityPlan.period <= f.period_to)
    return list(db.scalars(stmt))


def _brokers_by_id(db: Session, broker_ids: set[str]) -> dict[str, Broker]:
    if not broker_ids:
        return {}
    rows = db.scalars(select(Broker).where(Broker.broker_id.in_(broker_ids)))
    return {b.broker_id: b for b in rows}


def _latest_period(subs: list[BrokerSubmission]) -> str:
    if subs:
        return max(s.period for s in subs)
    now = _now()
    return f"{now.year}-{now.month:02d}"


# --- alert assembly ----------------------------------------------------------


def _aggregate_limit_alerts(
    subs: list[BrokerSubmission], plans: list[EntityPlan]
) -> list[ds.Alert]:
    """Concentration alerts: Σ top-client limit above the plan's aggregate_limit."""
    plan_by_key = {(p.entity_code, p.coverage, p.period): p for p in plans}
    limits: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: ZERO)
    for s in subs:
        if s.top_client_limit is not None:
            limits[(s.entity_code, s.coverage, s.period)] += s.top_client_limit

    alerts: list[ds.Alert] = []
    for key, total in sorted(limits.items(), key=lambda kv: kv[0][2], reverse=True):
        plan = plan_by_key.get(key)
        if plan is None or plan.aggregate_limit <= 0 or total <= plan.aggregate_limit:
            continue
        entity, coverage, period = key
        alerts.append(
            ds.Alert(
                type="aggregate_limit_breach",
                severity="red",
                entity_code=entity,
                coverage=coverage,
                period=period,
                message=(
                    f"{entity}/{coverage} {period}: top-client exposure {total} exceeds "
                    f"aggregate limit {plan.aggregate_limit}"
                ),
            )
        )
    return alerts


def _guardrail_alerts(subs: list[BrokerSubmission]) -> list[ds.Alert]:
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"amber": 0, "red": 0}
    )
    for s in subs:
        g = grouped[(s.entity_code, s.coverage, s.period)]
        g["amber"] += s.breach_count_amber
        g["red"] += s.breach_count_red

    alerts: list[ds.Alert] = []
    for (entity, coverage, period), counts in sorted(
        grouped.items(), key=lambda kv: kv[0][2], reverse=True
    ):
        if counts["red"] > 0:
            severity, detail = "red", f"{counts['red']} red / {counts['amber']} amber"
        elif counts["amber"] > 0:
            severity, detail = "amber", f"{counts['amber']} amber"
        else:
            continue
        alerts.append(
            ds.Alert(
                type="guardrail_breach",
                severity=severity,
                entity_code=entity,
                coverage=coverage,
                period=period,
                message=f"{entity}/{coverage} {period}: {detail} guardrail breaches",
            )
        )
    return alerts


def _hit_ratio_alerts(subs: list[BrokerSubmission], plans: list[EntityPlan]) -> list[ds.Alert]:
    plan_by_key = {(p.entity_code, p.coverage, p.period): p for p in plans}
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"binds": 0, "quotes": 0}
    )
    for s in subs:
        g = grouped[(s.entity_code, s.coverage, s.period)]
        g["binds"] += s.binds
        g["quotes"] += s.quotes

    alerts: list[ds.Alert] = []
    for key, counts in sorted(grouped.items(), key=lambda kv: kv[0][2], reverse=True):
        plan = plan_by_key.get(key)
        if plan is None:
            continue
        actual = agg.hit_ratio(counts["binds"], counts["quotes"])
        gap = agg.variance(actual, plan.expected_hit_ratio)
        if gap is None or gap >= 0:
            continue
        entity, coverage, period = key
        alerts.append(
            ds.Alert(
                type="hit_ratio_below_plan",
                severity="amber",
                entity_code=entity,
                coverage=coverage,
                period=period,
                message=(
                    f"{entity}/{coverage} {period}: hit ratio {actual:.3f} below "
                    f"plan {plan.expected_hit_ratio:.3f}"
                ),
            )
        )
    return alerts


# --- endpoints ----------------------------------------------------------------


@router.get("/dashboard/executive", response_model=ds.ExecutiveDashboard)
def executive(f: ListFilters = FiltersDep, db: Session = Depends(get_db)) -> ds.ExecutiveDashboard:
    subs = _submission_rows(db, f)
    plans = _plan_rows(db, f)
    latest = _latest_period(subs)
    months = agg.month_sequence(latest, 12)

    by_month: dict[str, dict] = {
        m: {"binds": 0, "quotes": 0, "gwp": ZERO, "plan_gwp": ZERO, "exposure": ZERO, "amber": 0, "red": 0}
        for m in months
    }
    totals = {"binds": 0, "quotes": 0, "gwp": ZERO, "plan_gwp": ZERO, "exposure": ZERO, "amber": 0, "red": 0}
    for s in subs:
        totals["binds"] += s.binds
        totals["quotes"] += s.quotes
        totals["gwp"] += s.gwp
        totals["exposure"] += s.total_limit
        totals["amber"] += s.breach_count_amber
        totals["red"] += s.breach_count_red
        if s.period in by_month:
            m = by_month[s.period]
            m["binds"] += s.binds
            m["quotes"] += s.quotes
            m["gwp"] += s.gwp
            m["exposure"] += s.total_limit
            m["amber"] += s.breach_count_amber
            m["red"] += s.breach_count_red
    for p in plans:
        totals["plan_gwp"] += p.plan_gwp
        if p.period in by_month:
            by_month[p.period]["plan_gwp"] += p.plan_gwp

    cur, prev = by_month.get(latest), by_month.get(agg.prev_period(latest))

    def _kpi(metric) -> ds.Kpi:
        return ds.Kpi(
            value=metric(totals),
            mom_trend=agg.mom_trend(
                metric(cur) if cur else None, metric(prev) if prev else None
            ),
        )

    kpis: dict[str, ds.Kpi | ds.MoneyKpi] = {
        "hit_ratio": _kpi(lambda t: agg.hit_ratio(t["binds"], t["quotes"])),
        "breach_pct": _kpi(lambda t: agg.breach_pct(t["amber"], t["red"], t["binds"])),
        "plan_attainment_gwp": _kpi(lambda t: agg.plan_attainment(t["gwp"], t["plan_gwp"])),
        "total_exposure": ds.MoneyKpi(
            value=str(totals["exposure"]),
            mom_trend=agg.mom_trend(
                float(cur["exposure"]) if cur else None,
                float(prev["exposure"]) if prev else None,
            ),
        ),
    }

    series = [
        ds.ExecutiveSeriesPoint(
            period=m,
            hit_ratio=agg.hit_ratio(by_month[m]["binds"], by_month[m]["quotes"]),
            gwp=str(by_month[m]["gwp"]),
            plan_gwp=str(by_month[m]["plan_gwp"]),
        )
        for m in months
    ]

    per_broker: dict[str, dict] = defaultdict(lambda: {"gwp": ZERO, "binds": 0, "quotes": 0})
    for s in subs:
        b = per_broker[s.broker_id]
        b["gwp"] += s.gwp
        b["binds"] += s.binds
        b["quotes"] += s.quotes
    top_ids = sorted(per_broker, key=lambda k: per_broker[k]["gwp"], reverse=True)[:5]
    registry = _brokers_by_id(db, set(top_ids))
    top_brokers = [
        ds.TopBroker(
            broker_id=bid,
            broker_name=registry[bid].broker_name if bid in registry else bid,
            tier=registry[bid].tier if bid in registry else None,
            gwp=str(per_broker[bid]["gwp"]),
            hit_ratio=agg.hit_ratio(per_broker[bid]["binds"], per_broker[bid]["quotes"]),
        )
        for bid in top_ids
    ]

    alerts = (
        _guardrail_alerts(subs) + _aggregate_limit_alerts(subs, plans) + _hit_ratio_alerts(subs, plans)
    )[:50]

    return ds.ExecutiveDashboard(
        as_of=_now(), filters=f.echo(), kpis=kpis, series=series,
        top_brokers=top_brokers, alerts=alerts,
    )


@router.get("/brokers", response_model=ds.BrokerLeaderboard)
def broker_leaderboard(
    f: ListFilters = FiltersDep, db: Session = Depends(get_db)
) -> ds.BrokerLeaderboard:
    subs = _submission_rows(db, f)
    latest = _latest_period(subs)
    months = agg.month_sequence(latest, 12)
    registry = _brokers_by_id(db, {s.broker_id for s in subs})

    grouped: dict[str, list[BrokerSubmission]] = defaultdict(list)
    for s in subs:
        grouped[s.broker_id].append(s)

    rows: list[ds.BrokerLeaderboardRow] = []
    for bid, items in grouped.items():
        broker = registry.get(bid)
        gwp = sum((s.gwp for s in items), ZERO)
        month_gwp = defaultdict(lambda: ZERO)
        for s in items:
            month_gwp[s.period] += s.gwp
        lr_pairs = [
            (s.incurred_loss_ratio, float(s.gwp))
            for s in items
            if s.incurred_loss_ratio is not None
        ]
        rows.append(
            ds.BrokerLeaderboardRow(
                broker_id=bid,
                broker_name=broker.broker_name if broker else bid,
                broker_group=broker.broker_group if broker else None,
                tier=broker.tier if broker else None,
                home_region=broker.home_region if broker else None,
                hit_ratio=agg.hit_ratio(sum(s.binds for s in items), sum(s.quotes for s in items)),
                gwp=str(gwp),
                brokerage=str(sum((s.brokerage for s in items), ZERO)),
                avg_premium_deviation=agg.weighted_avg(
                    [(s.avg_premium_deviation, float(s.binds)) for s in items]
                ),
                incurred_loss_ratio=agg.weighted_avg(lr_pairs),
                sparkline=[float(month_gwp[m]) for m in months],
            )
        )
    rows.sort(key=lambda r: Decimal(r.gwp), reverse=True)
    return ds.BrokerLeaderboard(
        as_of=_now(), filters=f.echo(), total=len(rows),
        rows=rows[f.offset : f.offset + f.limit],
    )


@router.get("/brokers/{broker_id}", response_model=ds.BrokerProfile)
def broker_profile(
    broker_id: str, f: ListFilters = FiltersDep, db: Session = Depends(get_db)
) -> ds.BrokerProfile:
    broker = db.get(Broker, broker_id)
    if broker is None:
        raise HTTPException(status_code=404, detail=f"unknown broker_id '{broker_id}'")

    items = [s for s in _submission_rows(db, f) if s.broker_id == broker_id]
    latest = _latest_period(items)
    months = agg.month_sequence(latest, 12)

    by_month: dict[str, list[BrokerSubmission]] = defaultdict(list)
    for s in items:
        by_month[s.period].append(s)
    monthly = [
        ds.BrokerMonthPoint(
            period=m,
            quotes=sum(s.quotes for s in by_month[m]),
            binds=sum(s.binds for s in by_month[m]),
            hit_ratio=agg.hit_ratio(
                sum(s.binds for s in by_month[m]), sum(s.quotes for s in by_month[m])
            ),
            gwp=str(sum((s.gwp for s in by_month[m]), ZERO)),
            brokerage=str(sum((s.brokerage for s in by_month[m]), ZERO)),
            avg_premium_deviation=agg.weighted_avg(
                [(s.avg_premium_deviation, float(s.binds)) for s in by_month[m]]
            ),
        )
        for m in months
    ]

    by_coverage: dict[str, list[BrokerSubmission]] = defaultdict(list)
    for s in items:
        by_coverage[s.coverage].append(s)
    coverages = [
        ds.BrokerCoverageRow(
            coverage=c,
            gwp=str(sum((s.gwp for s in rows), ZERO)),
            hit_ratio=agg.hit_ratio(sum(s.binds for s in rows), sum(s.quotes for s in rows)),
            binds=sum(s.binds for s in rows),
        )
        for c, rows in sorted(by_coverage.items())
    ]

    # Share of wallet (DP-03 precursor): this broker's GWP over its broker
    # group's GWP within the same filter window.
    share = None
    if broker.broker_group:
        group_ids = set(
            db.scalars(select(Broker.broker_id).where(Broker.broker_group == broker.broker_group))
        )
        group_subs = [s for s in _submission_rows(db, f) if s.broker_id in group_ids]
        share = agg.share_of_wallet(
            sum((s.gwp for s in items), ZERO), sum((s.gwp for s in group_subs), ZERO)
        )

    return ds.BrokerProfile(
        as_of=_now(), filters=f.echo(),
        broker_id=broker.broker_id, broker_name=broker.broker_name,
        broker_group=broker.broker_group, tier=broker.tier,
        home_region=broker.home_region, is_new=broker.is_new,
        share_of_wallet=share, monthly=monthly, coverages=coverages,
    )


@router.get("/dashboard/exposure", response_model=ds.ExposureDashboard)
def exposure(f: ListFilters = FiltersDep, db: Session = Depends(get_db)) -> ds.ExposureDashboard:
    subs = _submission_rows(db, f)
    plans = _plan_rows(db, f)

    def _grouped(attr: str) -> list[ds.NamedExposure]:
        grouped: dict[str, dict] = defaultdict(lambda: {"limit": ZERO, "gwp": ZERO})
        for s in subs:
            g = grouped[getattr(s, attr)]
            g["limit"] += s.total_limit
            g["gwp"] += s.gwp
        return [
            ds.NamedExposure(name=name, total_limit=str(v["limit"]), gwp=str(v["gwp"]))
            for name, v in sorted(grouped.items(), key=lambda kv: kv[1]["limit"], reverse=True)
        ]

    # Per-client concentration: a client can recur across months; take its
    # largest reported limit as the standing exposure (top-client granularity,
    # SPEC §4.3).
    client_limit: dict[str, dict] = {}
    for s in subs:
        if s.top_client_ref and s.top_client_limit is not None:
            cur = client_limit.get(s.top_client_ref)
            if cur is None or s.top_client_limit > cur["limit"]:
                client_limit[s.top_client_ref] = {
                    "limit": s.top_client_limit,
                    "industry": s.top_client_industry,
                    "entity": s.entity_code,
                }
    top_clients = [
        ds.TopClient(
            client_ref=ref, industry=v["industry"], total_limit=str(v["limit"]),
            entity_code=v["entity"],
        )
        for ref, v in sorted(client_limit.items(), key=lambda kv: kv[1]["limit"], reverse=True)[:10]
    ]
    limits = [v["limit"] for v in client_limit.values()]

    return ds.ExposureDashboard(
        as_of=_now(), filters=f.echo(), currency="USD",
        by_region=_grouped("region"), by_coverage=_grouped("coverage"),
        top_clients=top_clients,
        lorenz=[ds.LorenzPoint(**p) for p in agg.lorenz_points(limits)],
        gini=agg.gini(limits),
        alerts=_aggregate_limit_alerts(subs, plans)[:50],
    )


@router.get("/dashboard/guardrails", response_model=ds.GuardrailsDashboard)
def guardrails(
    threshold: float | None = Query(default=None, gt=0, description="What-if upper band"),
    f: ListFilters = FiltersDep,
    db: Session = Depends(get_db),
) -> ds.GuardrailsDashboard:
    subs = _submission_rows(db, f)
    plans = _plan_rows(db, f)
    plan_by_key = {(p.entity_code, p.coverage, p.period): p for p in plans}

    histogram = [
        ds.HistogramBucket(**b)
        for b in agg.deviation_histogram([(s.avg_premium_deviation, s.binds) for s in subs])
    ]

    per_coverage: dict[str, dict] = defaultdict(lambda: {"amber": 0, "red": 0, "binds": 0})
    for s in subs:
        c = per_coverage[s.coverage]
        c["amber"] += s.breach_count_amber
        c["red"] += s.breach_count_red
        c["binds"] += s.binds
    by_coverage = [
        ds.CoverageBreaches(
            coverage=cov, amber=v["amber"], red=v["red"], binds=v["binds"],
            breach_pct=agg.breach_pct(v["amber"], v["red"], v["binds"]),
        )
        for cov, v in sorted(per_coverage.items())
    ]

    breach_list = [
        ds.BreachRow(
            entity_code=s.entity_code, coverage=s.coverage, period=s.period,
            broker_id=s.broker_id, avg_premium_deviation=s.avg_premium_deviation,
            guardrail_low=(
                float(p.guardrail_low)
                if (p := plan_by_key.get((s.entity_code, s.coverage, s.period)))
                else None
            ),
            guardrail_high=(
                float(p.guardrail_high)
                if (p := plan_by_key.get((s.entity_code, s.coverage, s.period)))
                else None
            ),
            breach_count_amber=s.breach_count_amber, breach_count_red=s.breach_count_red,
        )
        for s in sorted(subs, key=lambda s: s.period, reverse=True)
        if s.breach_count_amber + s.breach_count_red > 0
    ][:100]

    what_if = None
    if threshold is not None:
        result = agg.what_if_breaches(
            [(s.avg_premium_deviation, s.binds) for s in subs], threshold
        )
        what_if = ds.WhatIf(threshold=threshold, lower_band=0.90, **result)

    return ds.GuardrailsDashboard(
        as_of=_now(), filters=f.echo(), histogram=histogram,
        by_coverage=by_coverage, breach_list=breach_list, what_if=what_if,
    )


@router.get("/dashboard/plan-vs-actual", response_model=ds.PlanVsActual)
def plan_vs_actual(
    f: ListFilters = FiltersDep, db: Session = Depends(get_db)
) -> ds.PlanVsActual:
    subs = _submission_rows(db, f)
    plans = _plan_rows(db, f)

    plan_grouped: dict[tuple[str, str], list[EntityPlan]] = defaultdict(list)
    for p in plans:
        plan_grouped[(p.entity_code, p.coverage)].append(p)
    sub_grouped: dict[tuple[str, str], list[BrokerSubmission]] = defaultdict(list)
    for s in subs:
        sub_grouped[(s.entity_code, s.coverage)].append(s)

    rows: list[ds.PlanVsActualRow] = []
    for key in sorted(set(plan_grouped) | set(sub_grouped)):
        entity, coverage = key
        p_rows, s_rows = plan_grouped.get(key, []), sub_grouped.get(key, [])

        plan_gwp = sum((p.plan_gwp for p in p_rows), ZERO)
        actual_gwp = sum((s.gwp for s in s_rows), ZERO)
        expected_hr = agg.weighted_avg(
            [(p.expected_hit_ratio, float(p.plan_gwp)) for p in p_rows]
        )
        actual_hr = agg.hit_ratio(sum(s.binds for s in s_rows), sum(s.quotes for s in s_rows))
        plan_lr = agg.weighted_avg([(p.plan_loss_ratio, float(p.plan_gwp)) for p in p_rows])
        actual_lr = agg.weighted_avg(
            [(s.incurred_loss_ratio, float(s.gwp)) for s in s_rows if s.incurred_loss_ratio is not None]
        )

        attainment = agg.plan_attainment(actual_gwp, plan_gwp)
        hr_variance = agg.variance(actual_hr, expected_hr)
        lr_variance = agg.variance(actual_lr, plan_lr)

        flags = []
        if attainment is not None and attainment < 1:
            flags.append("GWP_BELOW_PLAN")
        if hr_variance is not None and hr_variance < 0:
            flags.append("HIT_RATIO_BELOW_PLAN")
        if lr_variance is not None and lr_variance > 0:
            flags.append("LOSS_RATIO_ABOVE_PLAN")

        currency = p_rows[0].currency if p_rows else (s_rows[0].currency if s_rows else "USD")
        rows.append(
            ds.PlanVsActualRow(
                entity_code=entity, coverage=coverage, currency=currency,
                plan_gwp=str(plan_gwp), actual_gwp=str(actual_gwp),
                plan_attainment_gwp=attainment,
                expected_hit_ratio=expected_hr, hit_ratio=actual_hr,
                hit_ratio_variance=hr_variance,
                plan_loss_ratio=plan_lr, incurred_loss_ratio=actual_lr,
                loss_ratio_variance=lr_variance, flags=flags,
            )
        )
    return ds.PlanVsActual(as_of=_now(), filters=f.echo(), rows=rows)


@router.get("/entity-plans", response_model=ds.PagedResponse)
def browse_entity_plans(
    f: ListFilters = FiltersDep, db: Session = Depends(get_db)
) -> ds.PagedResponse:
    rows = _plan_rows(db, f)
    rows.sort(key=lambda p: (p.period, p.entity_code, p.coverage))
    page = rows[f.offset : f.offset + f.limit]
    return ds.PagedResponse(
        as_of=_now(), filters=f.echo(), total=len(rows), limit=f.limit, offset=f.offset,
        records=[EntityPlanOut.model_validate(p, from_attributes=True).model_dump() for p in page],
    )


@router.get("/broker-submissions", response_model=ds.PagedResponse)
def browse_broker_submissions(
    f: ListFilters = FiltersDep, db: Session = Depends(get_db)
) -> ds.PagedResponse:
    rows = _submission_rows(db, f)
    rows.sort(key=lambda s: (s.period, s.entity_code, s.broker_id, s.coverage))
    page = rows[f.offset : f.offset + f.limit]
    return ds.PagedResponse(
        as_of=_now(), filters=f.echo(), total=len(rows), limit=f.limit, offset=f.offset,
        records=[
            BrokerSubmissionOut.model_validate(s, from_attributes=True).model_dump() for s in page
        ],
    )
