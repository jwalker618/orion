# Project ORION — Broker Intelligence Demo API

A working demonstration backend for the Broker Relations Centre of Excellence /
Project ORION concept: **entities submit data → API validates and stores →
dashboards read aggregates**. See [SPEC.md](SPEC.md) for the full specification;
it is the source of truth.

Demo-grade on purpose: SQLite file database, API-key auth stub, no PII —
structured so the production upgrade path (Postgres, Entra ID, Azure Container
Apps) is a configuration change, not a rewrite (SPEC §10).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app          # dashboard at http://127.0.0.1:8000, Swagger at /docs
python scripts/seed.py        # loads 80 brokers × 12 months through the API
pytest                        # 58 tests; KPI math is 100% covered
```

Configuration via environment (or `.env`): `ORION_DATABASE_URL`
(default `sqlite:///./demo.db`), `ORION_API_KEYS` (comma-separated,
default `demo-key`), `ORION_CORS_ORIGINS` (default `*`).

All routes are prefixed `/api/v1` and, except `GET /health`, require the
`X-API-Key` header.

## Ingestion (curl examples)

**Entity plans** — one record per entity × coverage × period, upserted on
natural key (idempotent; identical re-POST is a no-op update):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/entity-plans \
  -H 'X-API-Key: demo-key' -H 'Content-Type: application/json' \
  -d '{"records": [{
        "entity_code": "MSRE", "coverage": "CYBER", "period": "2026-06",
        "plan_gwp": "1200000.00", "plan_brokerage": "240000.00",
        "expected_hit_ratio": 0.35, "plan_loss_ratio": 0.55,
        "guardrail_low": "0.90", "guardrail_high": "1.20",
        "aggregate_limit": "50000000.00"}]}'
# → {"accepted": 1, "updated": 0, "rejected": [], "warnings": []}
```

**Broker submissions** — monthly aggregated actuals per entity × broker ×
coverage × period. Unknown brokers auto-register when `broker_name` is given:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/broker-submissions \
  -H 'X-API-Key: demo-key' -H 'Content-Type: application/json' \
  -d '{"records": [{
        "entity_code": "MSRE", "broker_id": "BR-0001",
        "broker_name": "Alden Risk (001)", "tier": "PLATINUM",
        "coverage": "CYBER", "region": "UK", "period": "2026-06",
        "quotes": 24, "binds": 10, "gwp": "480000.00",
        "gwp_new": "120000.00", "gwp_renewal": "360000.00",
        "brokerage": "96000.00", "total_limit": "6500000.00",
        "avg_premium_deviation": 1.08,
        "breach_count_amber": 1, "breach_count_red": 0,
        "incurred_loss_ratio": 0.42,
        "top_client_ref": "CL-4821", "top_client_limit": "2400000.00",
        "top_client_industry": "TECHNOLOGY"}]}'
```

**Broker registry** (optional bulk upsert):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/reference/brokers \
  -H 'X-API-Key: demo-key' -H 'Content-Type: application/json' \
  -d '{"records": [{"broker_id": "BR-0001", "broker_name": "Alden Risk (001)",
        "broker_group": "Aegis Global", "tier": "PLATINUM",
        "home_region": "UK", "is_new": false}]}'
```

Batches accept partially: bad records come back itemised in `rejected[]` with
field-level errors; the rest are stored. Validation rules (SPEC §5) include
binds ≤ quotes, new+renewal ≈ gwp (±1%), closed entity/coverage lists, period
window (≤ current month +1), and a privacy guard that rejects anything but
anonymised `CL-xxxx` client refs.

## Dashboard read model

| Endpoint | Serves |
|---|---|
| `GET /api/v1/dashboard/executive` | KPI cards with MoM trend, 12-month series, top-5 brokers, alerts feed |
| `GET /api/v1/brokers` | leaderboard with 12-month GWP sparklines |
| `GET /api/v1/brokers/{broker_id}` | profile: monthly series, coverages, share of wallet |
| `GET /api/v1/dashboard/exposure` | exposure by region/coverage, top clients, Lorenz curve + Gini, limit-breach alerts |
| `GET /api/v1/dashboard/guardrails` | deviation histogram, amber/red by coverage, breach list; `?threshold=1.25` what-if |
| `GET /api/v1/dashboard/plan-vs-actual` | per entity × coverage plan vs actual with variance flags |
| `GET /api/v1/entity-plans`, `GET /api/v1/broker-submissions` | raw browse, filtered + paginated |
| `GET /api/v1/health` | status + record counts (no auth) |

Every list GET supports `entity`, `coverage`, `region`, `tier`, `period_from`,
`period_to`, `limit`, `offset`. Aggregate responses carry `as_of` and echo the
applied filters; money is returned as decimal strings with a currency.

## Demo data

`scripts/seed.py` generates the deterministic synthetic set (seed 42):
5 entities, 8 coverages, 80 tiered brokers, 12 months — Platinum brokers bind
at higher hit ratios and guardrail breaches concentrate in Cyber/Energy
(~8–10% amber+red). Seeding goes **through the public POST endpoints**, so
every seed run re-proves the ingestion path. `POST /api/v1/admin/reset`
truncates; `?reseed=true` reloads the same set through the same code path.

## Dashboard frontend

`frontend/` is the six-tab ORION dashboard, recreated from the Claude Design
handoff (`docs/design-handoff/`) and wired to the live read model. It is a
zero-build static app (ES modules + hand-built SVG charts on the Generate
design-token contract) served by FastAPI at `/`. All charts, KPIs, filters,
the broker profile modal, and the guardrails what-if slider run against
`/api/v1/*`; Market Perception and Operational Workflow are labelled
illustrative/demo-local per the honesty map. Light and dark themes.

## Layout

```
app/
├── main.py            # app assembly, CORS, RFC-7807-style error handlers
├── config.py          # pydantic-settings (DB url, API keys)
├── database.py        # engine/session; Postgres-portable
├── deps.py            # X-API-Key auth + shared list filters
├── models/            # SQLAlchemy: reference dims + the two facts
├── schemas/           # strict Pydantic contracts (extra="forbid", Decimal money)
├── routers/           # ingest, dashboard, admin — no KPI math in routers
└── services/
    ├── aggregation.py # ALL derived-metric math, pure + unit-tested
    ├── validation.py  # cross-field business rules (SPEC §5)
    └── demo_data.py   # deterministic synthetic generator (SPEC §6)
scripts/seed.py        # loads demo data via the API
tests/                 # ingest, aggregation, dashboard suites
frontend/              # six-tab dashboard (static, served at /)
├── tokens/            # Generate design-system token CSS (from the handoff)
├── css/app.css        # component layer transcribed from the design prototype
└── js/                # app shell, API client, formatters, SVG chart builders
```

## Integration notes

- [docs/design-handover.md](docs/design-handover.md) — UX handover for Claude
  Design: screen-by-screen contracts with real sample payloads, formatting
  conventions, shared component vocabulary, and states to design.
- [docs/integration-clearinghouse.md](docs/integration-clearinghouse.md) —
  how Clearinghouse Intelligence (multi-tenant submission intake) could feed
  this API's ingestion endpoints and share broker identity.
