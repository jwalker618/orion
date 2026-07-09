# Integration assessment: Clearinghouse Intelligence ↔ Project ORION

**Status:** investigation (no code built against Clearinghouse yet)
**Scope:** what a real integration would look like, what it would *not* be, and
what to align now so the two systems converge instead of drift.

## The two systems sit at different grains

| | Clearinghouse Intelligence | ORION demo API (this repo) |
|---|---|---|
| Unit of work | one **submission envelope** (an email, SFTP drop, portal upload) at intake time | one **monthly aggregate row** per entity × broker × coverage × period |
| Timing | real-time, at the front door of every channel | monthly reporting cadence |
| Knows about | who sent what, when, on which thread, with which attachments | quotes, binds, GWP, brokerage, pricing deviation, loss ratio |
| Does not know | underwriting outcomes (quoted? bound? at what premium?) | anything about individual documents or messages |

So the honest integration is **not** "Clearinghouse feeds ORION's
`POST /broker-submissions` directly" — the envelope contains no GWP, binds or
pricing. Those come from policy-admin/underwriting extracts (SPEC §10). The
real integration points are below, in order of value.

## 1. Shared broker identity (do this first, costs almost nothing)

Both systems maintain a broker registry and both suffer if `broker_id` means
different things:

- Clearinghouse: `clearinghouse.brokers.directory.BrokerDirectory` — operators
  load a CSV/JSON of `{id, name, domains, external_id, metadata}`; the enricher
  stamps a resolved `BrokerRef` onto every envelope. Unresolved domains can go
  to an external **webhook resolver** (`WebhookBrokerResolver`, expects
  `{"id", "name", "domains", "metadata"}` back).
- ORION: `brokers` table keyed by `broker_id`, fed by
  `POST /api/v1/reference/brokers` or auto-registered from submissions.

**Recommendation:** treat one broker directory as canonical and sync it both
ways:

- Export the Clearinghouse tenant's broker directory into ORION via
  `POST /api/v1/reference/brokers` (a ~30-line script: map `id → broker_id`,
  `name → broker_name`, `metadata.group → broker_group`,
  `metadata.tier → tier`). Run it on directory change or nightly.
- Optionally, stand a thin resolver endpoint in front of ORION's registry that
  answers the Clearinghouse webhook-resolver contract, so a broker added in
  ORION becomes resolvable at Clearinghouse intake without re-seeding CSVs.

With shared IDs, every Clearinghouse envelope is immediately joinable to
ORION's performance data — that is the DP-01/DP-03 join key.

## 2. Submission-flow metrics as a leading indicator (medium-term)

ORION's actuals (binds, GWP) are lagging indicators. Clearinghouse sees the
**incoming flow** — submissions per broker per coverage per month — weeks
before underwriting outcomes exist. Two clean mechanisms:

- **Destination adapter:** Clearinghouse routes envelopes to plugin
  destinations (`clearinghouse.destinations` entry point; webhook/S3 ship in
  core). A small `orion-bridge` webhook destination could receive envelopes,
  bucket counts by `(tenant → entity_code, broker.id, classification →
  coverage, month)`, and flush monthly.
- **Rules DSL:** Clearinghouse routing rules are CEL over the envelope
  (`submission.parties.broker.id`, `paper_type`, `placement`, artifact
  classification hints), so "route only new-business placement papers to the
  ORION bridge" is a one-line tenant rule, not code.

This would need one additive change on the ORION side — a
`submission_count`-style field or a third small fact ("broker flow"), since
counting envelopes is *not* the same as `quotes` (a submission received ≠ a
quote issued). Do not overload the existing `quotes` field with envelope
counts; keep the honesty map honest.

## 3. Alignment to adopt now (cheap, avoids future rework)

- **Entity mapping:** Clearinghouse is multi-tenant (`tenant_id` UUID); ORION
  entities are codes (`MSRE`, `AMLIN`…). Keep a `tenant_id ↔ entity_code` map
  in the bridge config, not in either schema.
- **Coverage vocabulary:** Clearinghouse classifies artifacts/submissions with
  tenant-defined tags; ORION has a closed 8-value coverage enum. Publish the
  ORION enum as the tag vocabulary for the tenant so rolled-up tags land on
  the enum without a translation table.
- **Anonymised client refs:** ORION rejects non-`CL-xxxx` client refs by
  design. Any bridge must anonymise before POSTing — Clearinghouse envelopes
  carry real party names/addresses, which must never cross into ORION.
- **Ack/report semantics:** both sides already speak "batch in → itemised
  accept/reject report out"; the bridge should propagate ORION's `rejected[]`
  entries back into Clearinghouse's audit trail rather than swallowing them.

## What not to build

- No document/claims ingestion into ORION (SPEC §1.3 — claims are Phase 3;
  ORION stays aggregate-grained and PII-free).
- No CRM/workflow coupling — Clearinghouse's operator console owns intake
  workflow; ORION's Operational Workflow tab is explicitly out of scope.

## Frontend note (generate-web as reference)

`generate-web` is a separate product suite, but its architecture is the right
template when ORION grows its own frontend: a monorepo platform
(`packages/` primitives + `apps/<product>` domains) with a strict
presentational/container split, where each product keeps its own personas and
palette on shared primitives. Its `ARCHITECTURE.md` already lists
`apps/clearinghouse-intelligence` as an upcoming product in that platform —
so the natural landing spot for an ORION dashboard UI is a sibling
`apps/` product consuming this API's `GET /dashboard/*` read model (which was
shaped for exactly that: the six-tab demo frontend). Until then, the existing
`broker-coe-demo.html` can be re-pointed at `GET /api/v1/dashboard/*`
per SPEC §8 milestone 7 (stretch).
