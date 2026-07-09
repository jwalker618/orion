# ORION UX handover — for Claude Design

**Audience:** Claude Design sessions building the ORION dashboard UX templates.
**Backend:** this repo (`broker-intel-api`), branch `claude/orion-buildout-4954g6` — built, tested, seeded.
**Status of this doc:** the design source of truth for ORION screens. ORION has no
`lens/` pack; this document plus the live API *is* the design input.

> **Relationship to generate-web:** ORION is a separate product, developed and hosted
> independently. Do **not** borrow DSI screen designs from `lens/`. What you *should*
> carry over from generate-web is its architecture discipline: presentational
> components with typed props + mock fixtures first, containers wiring real data later;
> product-owned palette on shared primitives. Every payload shape in this doc can be
> transcribed 1:1 into fixture files.

---

## 1. Product framing

ORION (Broker Relations Centre of Excellence) gives a reinsurance/insurance group a
single view of **broker performance against plan**. Reporting entities (MSRE, AMLIN,
MSEU, MSIJ, MSIGUSA) submit monthly plans and broker actuals; the dashboard answers:

- *Are we binding at the hit ratio we planned?*
- *Which brokers drive our book, and is their pricing inside the guardrails?*
- *Where is exposure concentrating — by region, coverage, client?*
- *Where are actuals diverging from plan?*

**Primary persona:** Broker Relations / Distribution lead at group level — scans KPIs,
drills into a broker, investigates alerts. Secondary: entity underwriting managers who
arrive pre-filtered to their entity.

### The six tabs and what the API feeds (honesty map)

| Tab | Fed by API? | Endpoint |
|---|---|---|
| 1. Executive Dashboard | ✅ fully | `GET /api/v1/dashboard/executive` |
| 2. Broker Performance | ✅ fully | `GET /api/v1/brokers` (+ `/brokers/{id}` for the profile modal) |
| 3. Exposure & Concentration | ✅ fully | `GET /api/v1/dashboard/exposure` |
| 4. Pricing & Guardrails | ✅ fully | `GET /api/v1/dashboard/guardrails` |
| 5. Market Perception | ⚠️ static seed only — design with hardcoded fixture, label as illustrative | — |
| 6. Operational Workflow | ⚠️ demo-local only — lightweight task list, no ingestion | — |
| (new) Plan vs Actual | ✅ fully | `GET /api/v1/dashboard/plan-vs-actual` |

Plan vs Actual is new relative to the original HTML demo — it can be a seventh tab or
a section within Executive; designer's call.

---

## 2. Global contracts (apply to every screen)

### Auth & errors
Every request needs header `X-API-Key` (demo key: `demo-key`); `GET /api/v1/health`
is open. Errors are RFC-7807-style `{type, title, detail, errors[]}` — design one
error surface that shows `title` and lists `errors[]`.

### Response conventions — these drive formatting components
- **Money is a decimal string** (`"68417285.27"`) with a `currency` (always `USD` in
  demo data). Parse with a decimal-safe formatter; display compact (`$68.4M`) with
  full value on hover/tooltip.
- **Ratios are floats 0–1** (`hit_ratio: 0.428` → render `42.8%`). Loss ratios can
  exceed 1 (bad year). `avg_premium_deviation` is a multiple around 1.0
  (`1.08` → render `×1.08` or `+8% vs technical`).
- **`null` means "no data", never zero.** A broker with no quotes has
  `hit_ratio: null` → render an em-dash `—`, not `0%`. This matters everywhere.
- **`mom_trend` is a relative month-on-month change** (`0.0094` = +0.9% vs last
  month). `null` = no prior month to compare → hide the trend chip.
- **Every aggregate response carries `as_of`** (UTC timestamp) **and `filters`**
  (echo of applied filters). Show "as of …" subtly; render active filters as
  removable chips from the echo.
- **Periods are ISO months** `"2026-07"` → display `Jul 2026`.

### Controlled vocabulary
- **Entities:** `MSRE` (Global), `AMLIN` (UK), `MSEU` (Europe), `MSIJ` (Japan),
  `MSIGUSA` (North America).
- **Coverages (8):** `PROPERTY, CASUALTY, MARINE, ENERGY, CYBER, DO, PI, FI`
  (DO = Directors & Officers, PI = Professional Indemnity, FI = Financial
  Institutions — spell out in tooltips, abbreviate in chips).
- **Tiers:** `PLATINUM > GOLD > SILVER > BRONZE` — a 4-step badge ramp, used in
  leaderboard rows, top-broker cards, profile header.
- **Alert severity:** `red` and `amber` only. Alert `type` is one of
  `guardrail_breach`, `aggregate_limit_breach`, `hit_ratio_below_plan`.
- **Regions (demo data):** UK, Europe, North America, Japan, APAC, LATAM,
  Middle East.

### The shared filter bar
Every list/aggregate GET accepts the same query params — design **one** FilterBar
used across all tabs: `entity`, `coverage`, `region`, `tier` (selects),
`period_from` / `period_to` (month pickers), plus `limit`/`offset` where tables
paginate. Changing a filter re-fetches the current tab with the params appended.

---

## 3. Screen-by-screen

Samples below are real responses from the seeded API (seed 42), trimmed with `…`.

### 3.1 Executive Dashboard — `GET /dashboard/executive`

```json
{
  "as_of": "2026-07-09T03:33:26Z",
  "filters": {"limit": 100, "offset": 0},
  "kpis": {
    "hit_ratio":           {"value": 0.3331, "mom_trend": 0.0094},
    "breach_pct":          {"value": 0.0975, "mom_trend": -0.1535},
    "plan_attainment_gwp": {"value": 0.9534, "mom_trend": 0.0100},
    "total_exposure":      {"value": "22898798951.02", "currency": "USD", "mom_trend": 0.0968}
  },
  "series": [
    {"period": "2025-08", "hit_ratio": 0.3312, "gwp": "104623918.44", "plan_gwp": "111905515.21"},
    "… 12 points total, oldest → newest …",
    {"period": "2026-07", "hit_ratio": 0.3340, "gwp": "122853053.84", "plan_gwp": "129241696.56"}
  ],
  "top_brokers": [
    {"broker_id": "BR-0001", "broker_name": "Denholm Risk (001)", "tier": "PLATINUM",
     "gwp": "68417285.27", "hit_ratio": 0.4282},
    "… 5 rows, sorted by GWP desc …"
  ],
  "alerts": [
    {"type": "guardrail_breach", "severity": "red", "entity_code": "AMLIN",
     "coverage": "CYBER", "period": "2026-07", "broker_id": null,
     "message": "AMLIN/CYBER 2026-07: 4 red / 16 amber guardrail breaches"},
    "… up to 50, guardrail first, then aggregate-limit, then hit-ratio-below-plan …"
  ]
}
```

**Layout:** 4 KPI cards → main chart → two side-by-side panels (top brokers, alerts).

- **KPI cards** (one template, two flavors): ratio KPI (`hit_ratio` 33.3%,
  `breach_pct` 9.7%, `plan_attainment_gwp` 95.3%) and money KPI
  (`total_exposure` $22.9B). Each shows a trend chip from `mom_trend`
  (↑/↓ + percent, green/red — note **breach_pct trending down is good**; direction
  semantics are per-KPI, so make "good direction" a prop on the card).
- **12-month series chart:** `gwp` vs `plan_gwp` as bars/area with `hit_ratio` as a
  line on a secondary axis — this is the plan-vs-actual heartbeat. Months with no
  data have `hit_ratio: null` and `"0"` money values.
- **Top-5 brokers:** compact ranked list — name, tier badge, GWP, hit ratio. Row
  links to the broker profile (tab 2).
- **Alerts feed:** severity dot + `message` + entity/coverage/period chips. Feed is
  capped at 50 — show "showing most recent" hint. Clicking a guardrail alert should
  deep-link to the Guardrails tab with entity+coverage filters applied.

### 3.2 Broker Performance — `GET /brokers`

```json
{
  "total": 80,
  "rows": [
    {"broker_id": "BR-0001", "broker_name": "Denholm Risk (001)", "broker_group": null,
     "tier": "PLATINUM", "home_region": "Europe",
     "hit_ratio": 0.4282, "gwp": "68417285.27", "brokerage": "13812067.54",
     "avg_premium_deviation": 1.0108, "incurred_loss_ratio": 0.6378,
     "sparkline": [6329426.02, "… 12 monthly GWP floats, oldest → newest …", 5508362.22]},
    "…"
  ]
}
```

**Layout:** FilterBar + leaderboard table, default sorted by GWP desc,
server-paginated (`total` + `limit`/`offset` → pager).

Columns: rank, broker (name + group subtext), tier badge, home region, hit ratio,
GWP, brokerage, pricing deviation (×1.01 style; subtle warn tint when outside
0.90–1.20), loss ratio (nullable → `—`), 12-mo sparkline (`sparkline` is plain
floats, oldest first — a tiny area/line, no axes). Row click opens the **profile
modal**.

### 3.3 Broker profile modal — `GET /brokers/{broker_id}`

```json
{
  "broker_id": "BR-0003", "broker_name": "Halvers Risk (003)",
  "broker_group": "Granite Bay", "tier": "PLATINUM", "home_region": "APAC",
  "is_new": false,
  "share_of_wallet": 0.5458,
  "monthly": [
    {"period": "2026-07", "quotes": 168, "binds": 65, "hit_ratio": 0.3869,
     "gwp": "5508362.22", "brokerage": "1158426.64", "avg_premium_deviation": 1.0559},
    "… 12 months …"
  ],
  "coverages": [
    {"coverage": "ENERGY", "gwp": "30729038.55", "hit_ratio": 0.4594, "binds": 181},
    "…"
  ]
}
```

- **Header:** name, tier badge, group, home region, optional `NEW` chip (`is_new`).
- **Share of wallet:** donut/bar — this broker's GWP as a share of its *group's* GWP
  (DP-03 precursor; 54.6% above). **`null` when the broker has no group** (~30% of
  brokers) — hide the element entirely, don't show 0%.
- **Monthly series:** quotes vs binds (bars) with hit-ratio line; GWP as a second
  panel or toggle.
- **Coverage split:** horizontal bars by GWP with hit ratio annotated.

### 3.4 Exposure & Concentration — `GET /dashboard/exposure`

```json
{
  "currency": "USD",
  "by_region":   [{"name": "Middle East", "total_limit": "5295609885.87", "gwp": "312023944.40"}, "…7 regions…"],
  "by_coverage": [{"name": "ENERGY", "total_limit": "8526140802.01", "gwp": "520844241.69"}, "…8…"],
  "top_clients": [
    {"client_ref": "CL-7375", "industry": "MANUFACTURING",
     "total_limit": "28220381.90", "entity_code": "MSIGUSA"}, "…10 rows…"
  ],
  "lorenz": [{"x": 0.0, "y": 0.0}, "… ~800 points, monotone concave-up …", {"x": 1.0, "y": 1.0}],
  "gini": 0.5515,
  "alerts": [
    {"type": "aggregate_limit_breach", "severity": "red", "entity_code": "AMLIN",
     "coverage": "CYBER", "period": "2025-10",
     "message": "AMLIN/CYBER 2025-10: top-client exposure 11616425.38 exceeds aggregate limit 10416508.78"}
  ]
}
```

- **Two ranked bar panels** (region, coverage), sorted by `total_limit` desc; GWP as
  secondary value. Reuse one "NamedExposure bars" component.
- **Top anonymised clients table:** `client_ref` (always `CL-xxxx` — privacy by
  design, never a real name), industry tag, limit, entity chip.
- **Lorenz curve:** plot `x` (cumulative share of clients) vs `y` (cumulative share
  of limit) against the y=x equality diagonal; annotate the Gini (0.55 = meaningful
  concentration). The array is dense (~one point per client) — safe to downsample
  for rendering.
- **Limit-breach alerts:** same Alert component as Executive.
- Honesty caveat for microcopy: client view is *top-client-per-submission*
  granularity, not a full client ledger.

### 3.5 Pricing & Guardrails — `GET /dashboard/guardrails?threshold=1.25`

```json
{
  "histogram": [
    {"low": null, "high": 0.8,  "label": "<0.80",      "count": 56},
    {"low": 0.95, "high": 1.0,  "label": "0.95–1.00",  "count": 4403},
    {"low": 1.0,  "high": 1.05, "label": "1.00–1.05",  "count": 5693},
    "… 9 buckets total …",
    {"low": 1.3,  "high": null, "label": "≥1.30",      "count": 17}
  ],
  "by_coverage": [
    {"coverage": "CYBER", "amber": 371, "red": 102, "binds": 2154, "breach_pct": 0.2196},
    "… CYBER ~22% and ENERGY ~18% dominate; others 3–9% …"
  ],
  "breach_list": [
    {"entity_code": "AMLIN", "coverage": "CYBER", "period": "2026-07", "broker_id": "BR-0001",
     "avg_premium_deviation": 0.9722, "guardrail_low": 0.9, "guardrail_high": 1.2,
     "breach_count_amber": 7, "breach_count_red": 0}
  ],
  "what_if": {"threshold": 1.25, "lower_band": 0.9, "breached_rows": 129, "breached_binds": 895}
}
```

- **Deviation histogram:** column chart over the 9 fixed bands; counts are weighted
  by binds (volume, not row count). Tint bands outside 0.90–1.20 amber/red; shade
  the guardrail zone. Bucketed by design — there is no per-policy scatter.
- **Amber/red by coverage:** stacked bars (amber+red) with `breach_pct` labels —
  this is the "breaches concentrate in Cyber/Energy" story.
- **Breach list:** table of breaching entity×coverage×broker×month rows, newest
  first, capped at 100. Show deviation against its band
  (e.g. dot on a 0.9–1.2 range strip). `guardrail_low/high` can be `null` when no
  plan exists for that cell → fall back to plain numbers.
- **What-if control:** the tab's signature interaction. A threshold slider
  (suggest 1.00–1.50, step 0.05, default off) refetches with `?threshold=` and
  shows `breached_rows` / `breached_binds`. Raising the threshold monotonically
  lowers the counts — an animated count-down as the user drags reads well.
  `what_if` is `null` when no threshold param is sent.

### 3.6 Plan vs Actual — `GET /dashboard/plan-vs-actual`

```json
{
  "rows": [
    {"entity_code": "MSRE", "coverage": "DO", "currency": "USD",
     "plan_gwp": "13600231.77", "actual_gwp": "13159793.27", "plan_attainment_gwp": 0.9676,
     "expected_hit_ratio": 0.3204, "hit_ratio": 0.3674, "hit_ratio_variance": 0.0470,
     "plan_loss_ratio": 0.4853, "incurred_loss_ratio": 0.5698, "loss_ratio_variance": 0.0845,
     "flags": ["GWP_BELOW_PLAN", "LOSS_RATIO_ABOVE_PLAN"]},
    "… one row per entity × coverage in filter range (≤40 unfiltered) …"
  ]
}
```

- **Matrix table** (or entity-grouped sections): per entity×coverage, three metric
  pairs — GWP (plan vs actual + attainment bar), hit ratio (expected vs actual ±
  variance), loss ratio (plan vs actual ± variance).
- **Flag pills** drive scanability: `GWP_BELOW_PLAN`, `HIT_RATIO_BELOW_PLAN`,
  `LOSS_RATIO_ABOVE_PLAN` — all "bad" flavored. No flags = quietly good.
- Variances are signed absolute deltas (`+0.047` hit ratio = 4.7pts above plan).
  Loss-ratio fields are `null` where no broker reported an LR.

### 3.7 Market Perception & Operational Workflow (no API)
Design both from static fixtures, visually consistent with the live tabs, with an
"illustrative data" affordance. Workflow is at most a local task list — do not
design ingestion or messaging flows (explicitly out of ORION scope).

---

## 4. Suggested shared component vocabulary

One template each, reused across tabs: `FilterBar`, `KpiCard` (+ `TrendChip` with
per-KPI good-direction), `SeriesChart` (12-month, money + ratio dual axis),
`Sparkline`, `LeaderboardTable` (server pagination), `TierBadge`, `AlertFeed` /
`AlertRow` (severity dot + chips), `NamedExposureBars`, `LorenzChart`,
`DeviationHistogram`, `BandedValue` (deviation dot on guardrail strip), `FlagPill`,
`MoneyText` (decimal-string-safe compact formatter), `RatioText` (null → `—`),
`AsOfStamp`.

## 5. States to design

- **Loading** per panel (cards/charts/tables skeletons).
- **Empty via filters** (e.g. `entity=MSIJ&coverage=MARINE` can return zero rows):
  chart renders 12 empty months, tables show "no records match these filters" with
  the filter chips visible.
- **Null metrics** (`—`, hidden trend chips, hidden share-of-wallet).
- **Auth failure (401)** and **validation error (422** on bad month input): render
  RFC-7807 `title` + `errors[]`.
- **Truncation hints:** alerts capped at 50, breach list at 100, top clients at 10.

## 6. Running against live data

```bash
pip install -e ".[dev]" && uvicorn app.main:app   # http://127.0.0.1:8000, CORS open
python scripts/seed.py                             # deterministic seed 42, ~2s
# header: X-API-Key: demo-key   |   Swagger: /docs
```

Useful truths about the seeded set for realistic mocks: 80 brokers (10 PLATINUM /
20 GOLD / 30 SILVER / 20 BRONZE), 12 months ending current month, group GWP
~$123M/mo vs plan ~$129M (attainment ~95%), overall hit ratio ~33% (Platinum ~43%,
Bronze ~22%), breach rate ~9.7% concentrated in CYBER/ENERGY, Gini ~0.55,
top broker `BR-0001 Denholm Risk` at $68.4M. `POST /api/v1/admin/reset?reseed=true`
restores this exact state.
