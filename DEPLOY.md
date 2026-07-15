# Deploying ORION to Railway + Vercel

The complete, current guide. ORION deploys the same way as the other Generate
assets: **Railway** runs the container (FastAPI + SQLite + the built-in
dashboard), **Vercel** optionally fronts the static dashboard on your usual
domain and proxies `/api/*` to Railway. Two topologies:

| Topology | What you get | When to pick it |
|---|---|---|
| **A · Railway only** | One service, one URL — dashboard at `/`, API at `/api/v1`, Swagger at `/docs` | Fastest demo; nothing else needed |
| **B · Railway + Vercel** | Vercel serves `frontend/` and rewrites `/api/*` to Railway (same-origin, no CORS) | Matches the generate-web pattern; Vercel domain, previews, edge caching for the static shell |

Topology B is additive — do A first, then put Vercel in front.

## What you need before starting

| Secret / value | How to get it |
|---|---|
| `ORION_API_KEYS` | Invent it: `openssl rand -hex 16`. Comma-separate to issue several keys. The demo default is `demo-key` — always override it for anything public. |
| Railway account + GitHub repo access | Railway → New Project → Deploy from GitHub |
| (B only) Vercel account | vercel.com, or `npm i -g vercel` for the CLI |

No other secrets: the demo has no OAuth, no PII, and SQLite needs no database
service.

## 1 · Railway — create the service

1. Railway → **New Project → Deploy from GitHub repo → `jwalker618/orion`**.
2. In the service **Settings** before the first build finishes:
   - **Config file path** → `railway.json` (applies the Dockerfile builder,
     the `/api/v1/health` healthcheck, restart-on-failure).
   - **Root Directory** → leave **empty** (the Dockerfile expects repo root).
   - **Branch** → whichever you deploy from; pushes to it auto-deploy.

## 2 · Variables

| Variable | Value | Why |
|---|---|---|
| `ORION_API_KEYS` | your secret key(s) | Replaces `demo-key` for **machine** callers (entity feeds, seed script, curl). |
| `ORION_AUTH_SECRET` | `openssl rand -hex 32` | Signs user access tokens. Override for anything public; restarts with a changed secret sign everyone out (by design). |
| `ORION_DEMO_PASSWORD` | your choice | Initial password for the seeded accounts (see README §Logins). Default `orion-demo`. |
| `ORION_LOGIN_NOTIFY_WEBHOOK_URL` | Slack incoming-webhook URL | Optional — posts "🔓 ORION login — …" on every fresh sign-in (same pattern as the DSI `LOGIN_NOTIFY_WEBHOOK_URL`, which is also accepted). Server-only, best-effort. |
| `ORION_SEED_ON_START` | `true` | Loads the deterministic demo set (seed 42) at boot whenever the DB is empty — an ephemeral-filesystem deploy is demo-ready on every restart. Skip it if you attach a volume and want to manage data yourself. |
| `ORION_DATABASE_URL` | `sqlite:////data/orion.db` | **Only with a volume** (step 3). Omit for ephemeral + seed-on-start. |
| `ORION_CORS_ORIGINS` | `https://your-app.vercel.app` | **Only for topology B without the rewrite** (frontend calling Railway cross-origin). With the Vercel rewrite (recommended) or topology A, leave the default `*` or tighten it — same-origin requests don't need CORS. |

Do **not** set `PORT` — Railway injects it and the container binds to it.

## 3 · (Optional) volume for persistence

Ingested data survives deploys only if you attach a volume: Service →
**Attach Volume**, mount path **`/data`**, then set
`ORION_DATABASE_URL=sqlite:////data/orion.db` (note the four slashes). Without
it the filesystem resets on every deploy — fine for a demo when
`ORION_SEED_ON_START=true` rebuilds the dataset in ~2 s at boot. The Postgres
upgrade path is the same variable pointed at a Railway Postgres service
(`postgresql://…`) plus `psycopg` in `pyproject.toml` — the SQLAlchemy models
are already portable.

## 4 · Networking & first deploy

- **Settings → Networking → Generate Domain.** Any port value works — the app
  reads Railway's injected `PORT`.
- Watch the deploy: healthcheck goes green when
  `https://<railway-domain>/api/v1/health` returns
  `{"status":"ok","db":"ok","records":{…}}` — with seed-on-start the record
  counts land at 480 plans / ~2,850 submissions.
- Open `https://<railway-domain>/` — you land on the ORION **login screen**;
  sign in with a demo identity (README §Logins) and `ORION_DEMO_PASSWORD`.
  Swagger is at `/docs`. (`?key=` is still accepted for direct API testing;
  the dashboard itself authenticates users with bearer tokens.)

**Topology A stops here.**

## 5 · Vercel — front the dashboard (topology B)

The frontend is a zero-build static app, so the Vercel project is trivial:

1. Edit `frontend/vercel.json`: replace the rewrite destination with your
   Railway domain (from step 4). Commit and push. The rewrite makes `/api/*`
   same-origin from the browser's point of view — no CORS, and the Railway
   URL never appears client-side.
2. Vercel → **Add New Project → import `jwalker618/orion`**:
   - **Root Directory** → `frontend`
   - **Framework Preset** → `Other`; leave Build Command and Output Directory
     **empty** (static files, nothing to build)
3. Deploy, then open `https://<vercel-domain>/` and sign in.

CLI equivalent: `cd frontend && vercel --prod` (answers: no build, root is the
directory itself).

### Fallback without the rewrite

If you'd rather point the frontend straight at Railway (no proxy), skip the
`vercel.json` edit and open
`https://<vercel-domain>/?key=<key>&api=https://<railway-domain>/api/v1` —
the dashboard stores the API base too. Then you **must** set
`ORION_CORS_ORIGINS=https://<vercel-domain>` on Railway.

## 6 · Slack login notifications

**Where this lives, and why it differs from DSI.** In generate-web/DSI the
frontend is a Next.js app, so its server code (the `/api/login-notify` route)
runs *on Vercel* — that's why `LOGIN_NOTIFY_WEBHOOK_URL` sat in the Vercel
project's environment variables. ORION's Vercel project is **static files
only** — there is no server code on Vercel to call Slack. The server here is
the FastAPI container on **Railway**, and the login endpoint itself sends the
notification. So:

> **The webhook variable goes on Railway. Vercel needs no configuration for
> this feature — in either topology.**

### Step 1 — get a Slack incoming-webhook URL

If you already have the DSI webhook and want ORION logins in the **same
channel**, skip to step 2 and paste that same URL — it works as-is.

For a fresh one (or a separate `#orion-logins` channel):

1. Go to <https://api.slack.com/apps> → **Create New App → From scratch** —
   name it e.g. `ORION login notify`, pick your workspace.
2. In the app's sidebar: **Incoming Webhooks** → toggle **Activate Incoming
   Webhooks** on.
3. **Add New Webhook to Workspace** → choose the channel to post into →
   **Allow**.
4. Copy the generated URL — it looks like
   `https://hooks.slack.com/services/<team-id>/<webhook-id>/<token>`.

Treat the URL as a secret (anyone holding it can post to the channel). It
stays server-side on Railway and never reaches the browser.

### Step 2 — set the variable on Railway

Railway → your ORION service → **Variables** → add:

```
ORION_LOGIN_NOTIFY_WEBHOOK_URL = <the URL you copied in step 1>
```

(The bare `LOGIN_NOTIFY_WEBHOOK_URL` name is also accepted, so a copy-pasted
variable from the DSI Vercel project works unchanged.) Save — Railway
redeploys automatically.

### Step 3 — test it

Sign in on the dashboard, or from a terminal:

```bash
curl -s -X POST https://<railway-domain>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo.user@msinternational.com","password":"<ORION_DEMO_PASSWORD>"}' > /dev/null
```

Within a second or two the channel receives:

> 🔓 **ORION login** — Demo User (demo.user@msinternational.com) · broker_relations · MS International
> 203.0.113.7 · Mozilla/5.0 (…) · 2026-07-15T09:10:51Z

Notes on behaviour (same contract as DSI): unset variable = feature off; a
down or rotated webhook is swallowed and never fails a login; for MFA users
the message fires when the challenge passes, not at password entry; the
notification runs as a background task after the login response, so it adds
no login latency.

| Not seeing messages? | Check |
|---|---|
| Nothing posts at all | Variable set on **Railway** (not Vercel)? Redeployed since setting it? Correct service? |
| Posted to the wrong channel | The channel is baked into the webhook URL at creation — make a new webhook for a different channel. |
| Works locally, not deployed | Local `.env` vs Railway Variables are separate — set it in both places you run the API. |
| `invalid_token` in Railway logs | Webhook was revoked/rotated in Slack — mint a new one and update the variable. |

## 7 · Verify

```bash
# API up and seeded
curl https://<railway-domain>/api/v1/health
# Auth enforced (expect 401)
curl -s -o /dev/null -w '%{http_code}\n' https://<railway-domain>/api/v1/brokers
# Dashboard read model
curl -H "X-API-Key: <key>" "https://<railway-domain>/api/v1/dashboard/executive" | head -c 300
```

Then click through the dashboard: all four API-fed tabs render, the guardrails
what-if slider changes the breach counts, and a broker row opens the profile
modal.

## Day-2 notes

- **Updating:** push to the deploy branch — Railway rebuilds the container,
  Vercel redeploys the static frontend. There is no schema migration tooling
  (demo-grade); destructive model changes need a wiped volume or a reset.
- **Reset / reseed on demand:** `curl -X POST -H "X-API-Key: <key>"
  "https://<railway-domain>/api/v1/admin/reset?reseed=true"`.
- **Rotating keys:** update `ORION_API_KEYS` (comma-separate during
  handover), redeploy, then re-open the dashboard with `?key=`.
- **Sleeping:** Railway's app-sleep is fine for this service (no long-lived
  state in memory); first request after a sleep pays the cold start + reseed.
- **The API key is demo-grade** — it ships to the browser, so treat the
  deployment as a demo, not a tenant boundary (SPEC §1.2: auth stub by
  design; the upgrade path is Entra ID).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Healthcheck never green | Config file path not set to `railway.json`, or Root Directory not empty — the image must build from repo root. |
| Dashboard bounces to the login screen after a deploy | `ORION_AUTH_SECRET` changed (or defaulted) — sessions are signed with it; sign in again. |
| Password reset asks for a token | Demo has no mailer — the token is printed in the Railway deploy log (`[orion-auth] password reset for …`). |
| Panels show "Network error" on Vercel | `vercel.json` rewrite destination still the placeholder, or the fallback mode is missing `ORION_CORS_ORIGINS` on Railway. |
| Data vanished after a deploy | Ephemeral filesystem without `ORION_SEED_ON_START=true` — set it, or attach a volume (step 3). |
| Fonts look like system-ui | IBM Plex loads from Google Fonts; blocked networks fall back gracefully. Self-host the fonts in `frontend/tokens/fonts.css` if needed. |
