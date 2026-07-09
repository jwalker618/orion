# Broker Intelligence Demo — FastAPI Backend Specification

**Version:** 1.0
**Status:** Ready for development
**Target tooling:** Claude Code
**Owner:** John
**Related artefacts:** `broker-coe-demo.html` (frontend demo), Project ORION v3.1 business case

---

## 1. Purpose & Goals

### 1.1 What this is

A working demonstration backend for the Broker Relations Centre of Excellence / Project ORION concept. It replaces the synthetic in-browser data of the existing HTML demo with a real ingestion-and-serving API, proving the end-to-end pattern: **entities submit data → API validates and stores → dashboards read aggregates**.

### 1.2 Exact goals

1. **Prove the ingestion pattern.** Two POST endpoints through which reporting entities (MSRe, Amlin, MS Europe, MSIJ, MSIG USA, etc.) can submit (a) entity-level plan data and (b) detailed broker/coverage actuals.
2. **Serve the dashboard.** GET endpoints that return pre-aggregated JSON shaped for the six tabs of the existing HTML demo, so the demo frontend can be re-pointed from its internal generator to this API with minimal change.
3. **Demonstrate plan-vs-actual intelligence.** The core analytical value: actual hit ratios, loss ratios, premiums and pricing deviations compared against submitted plans and guardrail bands, with breach detection.
4. **Stay ORION-aligned.** Field names and entity concepts follow the ORION v3.1 data dictionary (broker, broker group, GWP, brokerage, new/renewal, product line/coverage, country/region, entity, period) so the demo is a credible precursor to DP-01 (Broker Performance Core), DP-02 (Growth & Strategic Performance) and DP-03 (Share of Wallet).
5. **Be demo-grade, not production-grade — deliberately.** Single-file database, API-key auth stub, no PII. But structured so the upgrade path (Postgres, real auth, Azure deployment) is obvious and documented.

### 1.3 Non-goals (explicit)

- **No NPS/sentiment ingestion.** Market Perception data is out of ORION scope; the dashboard tab may be served from a static/optional seed only. Do not build a survey pipeline.
- **No workflow/CRM engine.** The Operational Workflow tab (kanban, SLA, messaging) is explicitly out of ORION scope (v3.1 Appendix 9). Provide at most a lightweight in-app task list persisted locally — not an ingestion channel.
- **No real client identities.** Client references are anonymised codes (ORION privacy-by-design). Reject any payload field that looks like personal data.
- **No authentication beyond API key.** No OAuth/AAD in this demo.
- **No claims-transaction ingestion.** Loss ratio arrives as a pre-computed ratio or incurred amount on submissions, not as claims records (claims detail is ORION Phase 3).

---

## 2. Architecture & Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Ubiquitous, Claude Code friendly |
| Framework | FastAPI + Uvicorn | Auto OpenAPI docs, Pydantic validation |
| Validation | Pydantic v2 | Strict schemas, good error messages |
| ORM / DB | SQLAlchemy 2.x + SQLite (file: `demo.db`) | Zero-install; swap to Postgres via connection string |
| Testing | pytest + httpx TestClient | Full endpoint coverage |
| Seed data | `scripts/seed.py` | Port of the HTML demo's synthetic generator |
| CORS | Enabled for `*` (demo) | Lets the HTML demo call the API from file:// or localhost |
| Docs | Built-in `/docs` (Swagger) + this spec | Self-describing API |

### 2.1 Project structure

```
broker-intel-api/
├── CLAUDE.md                  # Claude Code working instructions (§9)
├── SPEC.md                    # this document
├── pyproject.toml
├── app/
│   ├── main.py                # FastAPI app, routers, CORS, exception handlers
│   ├── config.py              # settings (DB url, API keys) via pydantic-settings
│   ├── database.py            # engine, session, init
│   ├── models/                # SQLAlchemy models
│   │   ├── entity_plan.py
│   │   ├── broker_submission.py
│   │   └── reference.py       # entities, coverages, brokers registry
│   ├── schemas/               # Pydantic request/response schemas
│   │   ├── plans.py
│   │   ├── submissions.py
│   │   └── dashboard.py
│   ├── routers/
│   │   ├── ingest.py          # the two POSTs + reference data POST
│   │   ├── dashboard.py       # aggregate GETs per tab
│   │   └── admin.py           # health, reset, seed trigger
│   └── services/
│       ├── aggregation.py     # all KPI math lives here, unit-tested
│       └── validation.py      # cross-field business rules
├── scripts/
│   └── seed.py                # synthetic data loader (80 brokers, 12 months)
└── tests/
    ├── test_ingest.py
    ├── test_dashboard.py
    └── test_aggregation.py
```

---

## 3. Data Model

### 3.1 Reference dimensions

**Entity** — reporting business unit.
`entity_code` (PK, e.g. `MSRE`, `AMLIN`, `MSEU`, `MSIJ`, `MSIGUSA`), `entity_name`, `region`.

**Coverage** (= line of business) — controlled vocabulary seeded from the demo:
`PROPERTY, CASUALTY, MARINE, ENERGY, CYBER, DO, PI, FI` (+ description).

**Broker** — registry, upserted on first sight or via reference POST:
`broker_id` (PK), `broker_name`, `broker_group` (e.g. group parent), `tier` (`PLATINUM|GOLD|SILVER|BRONZE`), `home_region`, `is_new` (bool).

**Period** — all facts carry `period` as ISO month string `YYYY-MM`. No free-text dates.

### 3.2 Fact 1: EntityPlan (from POST /entity-plans)

One row per **entity × coverage × period** (natural key; upsert on conflict).

| Field | Type | Notes |
|---|---|---|
| entity_code | str FK | required |
| coverage | enum FK | required |
| period | YYYY-MM | required |
| currency | ISO-4217 | default USD |
| plan_gwp | decimal ≥ 0 | plan gross written premium |
| plan_brokerage | decimal ≥ 0 | expected brokerage/commission |
| expected_hit_ratio | 0–1 | expected binds ÷ quotes |
| expected_bind_count | int ≥ 0 | optional |
| plan_loss_ratio | 0–2 | planned |
| guardrail_low | decimal > 0 | premium-deviation lower band (e.g. 0.90) |
| guardrail_high | decimal > guardrail_low | upper band (e.g. 1.20) |
| aggregate_limit | decimal ≥ 0 | exposure threshold for concentration alerts |
| notes | str ≤ 500 | optional |

### 3.3 Fact 2: BrokerSubmission (from POST /broker-submissions)

One row per **entity × broker × coverage × period** (natural key; upsert). Monthly aggregated actuals — not policy-level transactions (keeps the demo honest about ORION's aggregated scope and sidesteps PII).

| Field | Type | Notes |
|---|---|---|
| entity_code | str FK | required |
| broker_id | str | required; broker auto-registered if unknown when `broker_name` supplied |
| broker_name / broker_group / tier | str | optional; used for registry upsert |
| coverage | enum | required |
| region | str | market region of the business |
| period | YYYY-MM | required |
| currency | ISO-4217 | default USD |
| quotes | int ≥ 0 | quote count |
| binds | int ≥ 0 | must be ≤ quotes |
| gwp | decimal ≥ 0 | actual GWP |
| gwp_new / gwp_renewal | decimal ≥ 0 | must sum ≈ gwp (±1% tolerance) if both present |
| brokerage | decimal ≥ 0 | actual brokerage paid |
| total_limit | decimal ≥ 0 | exposure written |
| avg_premium_deviation | decimal > 0 | actual ÷ technical price, e.g. 1.08 |
| breach_count_amber / breach_count_red | int ≥ 0 | policies outside guardrail (amber ≤10% out, red >10%) |
| incurred_loss_ratio | 0–5, optional | actual LR where known |
| top_client_ref | str, optional | anonymised code (`CL-xxxx`) for concentration view |
| top_client_limit | decimal ≥ 0 | limit on that client |
| top_client_industry | enum, optional | industry sector |

### 3.4 Derived metrics (computed in `services/aggregation.py`, never stored)

- `hit_ratio = Σbinds / Σquotes` (guard div-zero → null)
- `plan_attainment_gwp = Σgwp / Σplan_gwp`
- `hit_ratio_variance = hit_ratio − expected_hit_ratio`
- `loss_ratio_variance = incurred_lr − plan_loss_ratio`
- `breach_pct = (amber + red) / binds`
- `share_of_wallet(broker) = broker gwp ÷ broker-group total gwp` (DP-03 precursor)
- Concentration: Lorenz points over `top_client_limit`; alert where Σ client limit > entity `aggregate_limit`

---

## 4. API Specification

All routes prefixed `/api/v1`. Auth: header `X-API-Key` checked against configured keys; 401 otherwise. All list GETs support `entity`, `coverage`, `region`, `tier`, `period_from`, `period_to` query filters plus `limit/offset` pagination.

### 4.1 Ingestion

**`POST /entity-plans`** — batch of 1–500 EntityPlan records.
Body: `{ "records": [EntityPlan, ...] }`
Behaviour: validate all → upsert by natural key → return `207`-style report:
`{ "accepted": n, "updated": n, "rejected": [{index, key, errors[]}] }`
Partial acceptance is allowed; rejects itemised with field-level Pydantic errors.

**`POST /broker-submissions`** — batch of 1–1000 BrokerSubmission records.
Same envelope, same upsert-and-report semantics. Cross-field rules (binds ≤ quotes; new+renewal ≈ gwp; guardrail sanity) enforced in `services/validation.py` and reported per record.

**`POST /reference/brokers`** — optional bulk broker registry upsert.

**Idempotency:** identical re-POST of a batch is a no-op update; safe to retry.

### 4.2 Dashboard serving (read model)

| Endpoint | Serves demo tab | Returns |
|---|---|---|
| `GET /dashboard/executive` | Executive Dashboard | KPI cards (hit ratio, total exposure, breach %, plan attainment) each with value + MoM trend; 12-month series (hit ratio, gwp, plan_gwp); top-5 brokers; alerts feed (guardrail breaches, aggregate-limit breaches, hit-ratio-below-plan) |
| `GET /brokers` | Broker Performance | leaderboard rows: broker, group, tier, region, hit_ratio, gwp, brokerage, avg_premium_deviation, lr (if any), 12-mo sparkline array |
| `GET /brokers/{broker_id}` | Broker profile modal | full monthly series + coverages + share_of_wallet |
| `GET /dashboard/exposure` | Exposure & Concentration | exposure by region, by coverage, top anonymised clients, Lorenz curve points, limit-breach alerts |
| `GET /dashboard/guardrails` | Pricing & Guardrails | deviation histogram buckets, amber/red by coverage, breach list vs plan bands, what-if: `?threshold=1.25` recomputes breach counts server-side |
| `GET /dashboard/plan-vs-actual` | (new view) | per entity×coverage: plan vs actual gwp, hit ratio, LR with variance flags |
| `GET /entity-plans`, `GET /broker-submissions` | raw browse | filtered, paginated records |
| `GET /health` | — | `{status, db, records:{plans,submissions}}` |

**Response conventions:** money as decimal strings with `currency`; ratios as floats 0–1; every aggregate response carries `as_of` and applied `filters` echo. Errors follow RFC-7807-style `{type,title,detail,errors[]}`.

### 4.3 Tab coverage honesty map

| Demo tab | Fed by this API? |
|---|---|
| Executive Dashboard | ✅ fully |
| Broker Performance | ✅ fully |
| Exposure & Concentration | ✅ fully (client view limited to top-client-per-submission granularity) |
| Pricing & Guardrails | ✅ fully (bucketed, not per-policy scatter) |
| Market Perception | ⚠️ static seed only — out of ingestion scope |
| Operational Workflow | ⚠️ demo-local only — out of ORION scope |

---

## 5. Validation & Business Rules

1. Schema validation (types, ranges, enums) — Pydantic, automatic.
2. `binds ≤ quotes`; reject otherwise.
3. `gwp_new + gwp_renewal` within ±1% of `gwp` when all three present.
4. `guardrail_low < 1.0 ≤ guardrail_high` sanity warning (accepted with `warnings[]` in report, not rejected).
5. Unknown `entity_code` → reject (entities are a closed list, seeded).
6. Unknown `coverage` → reject.
7. Unknown `broker_id` without `broker_name` → reject; with name → auto-register.
8. Period must be `YYYY-MM`, not in the future beyond +1 month.
9. Any field matching an email/phone/name-like pattern in `top_client_ref` → reject (privacy guard).

---

## 6. Seed & Demo Data Strategy

`scripts/seed.py` ports the HTML demo generator: **5 entities, 8 coverages, 80 brokers (tiered), 12 months**, correlations preserved (Platinum → higher hit ratio; breaches concentrated in Cyber/Energy; ~8% amber+red). It seeds via the public POST endpoints, not direct DB writes — so seeding itself exercises and proves the ingestion path. Deterministic seed (42) for reproducible demos. `POST /admin/reset` (API-key-gated) truncates and reseeds.

---

## 7. Testing & Acceptance Criteria

**Test plan (pytest):**
- Ingestion: happy path, each validation rule, partial-batch rejection report, idempotent re-POST, upsert-overwrites.
- Aggregation unit tests: known small fixture → hand-computed hit ratio, breach %, Lorenz points, plan variance.
- Dashboard: every GET returns 200 with schema-valid body against seeded DB; filters actually filter; what-if threshold changes breach counts monotonically.
- Auth: 401 without key.

**Acceptance (demo is "done" when):**
1. `uvicorn app.main:app` starts clean; `/docs` renders all endpoints.
2. `python scripts/seed.py` loads full synthetic set via the API in < 60s.
3. Every dashboard GET returns data matching the seeded fixture expectations.
4. Test suite green; ≥ 85% coverage on `services/`.
5. A curl example for each POST is documented in README and works.
6. (Stretch) `broker-coe-demo.html` modified to fetch from `GET /dashboard/*` renders tabs 1–4 from live API data.

---

## 8. Delivery Plan (Claude Code milestones)

| # | Milestone | Contents |
|---|---|---|
| 1 | Skeleton | project structure, config, DB init, health endpoint, auth dependency |
| 2 | Reference + Plans | entity/coverage/broker models, `POST /entity-plans` + GET, tests |
| 3 | Submissions | `POST /broker-submissions` full validation, tests |
| 4 | Aggregation core | `services/aggregation.py` + unit tests (do this before routers that use it) |
| 5 | Dashboard GETs | executive, brokers, exposure, guardrails, plan-vs-actual |
| 6 | Seed + polish | seed script through the API, README with curl examples, reset endpoint |
| 7 | (Stretch) Frontend wiring | point the HTML demo at the API |

Each milestone: code + tests + one-line README update, committed separately.

---

## 9. CLAUDE.md guidance (place in repo root)

```markdown
# Working rules
- Read SPEC.md before any change; it is the source of truth.
- All KPI math lives in app/services/aggregation.py with unit tests. Never
  compute KPIs inline in routers.
- Pydantic schemas are strict: extra="forbid". Money = Decimal, never float.
- Natural-key upserts everywhere; POSTs must be idempotent.
- Run `pytest -q` after every milestone; do not proceed on red.
- No PII anywhere. Client refs are anonymised codes only.
- SQLite now, but write SQLAlchemy portable to Postgres (no SQLite-only types).
```

---

## 10. Upgrade path (documented, not built)

SQLite → Azure SQL/Postgres (connection string only) · API key → Entra ID · Uvicorn → Azure Container Apps · seed script → real entity extracts mapped to the same two POST schemas · this API's read model → the Power BI/Fabric semantic layer in ORION Phase 1.
