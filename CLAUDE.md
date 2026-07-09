# Working rules

- Read SPEC.md before any change; it is the source of truth.
- All KPI math lives in app/services/aggregation.py with unit tests. Never
  compute KPIs inline in routers.
- Pydantic schemas are strict: extra="forbid". Money = Decimal, never float.
- Natural-key upserts everywhere; POSTs must be idempotent.
- Run `pytest -q` after every milestone; do not proceed on red.
- No PII anywhere. Client refs are anonymised codes only.
- SQLite now, but write SQLAlchemy portable to Postgres (no SQLite-only types).
