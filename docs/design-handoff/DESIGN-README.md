# Handoff: ORION — Broker Relations Dashboard

## Overview
ORION (Broker Relations Centre of Excellence) is a group-level analytics dashboard that shows
broker performance against plan for a reinsurance/insurance group (reporting entities: MSRE,
AMLIN, MSEU, MSIJ, MSIGUSA — an MS&AD-style group). The primary user is a Broker Relations /
Distribution lead who scans KPIs, drills into a broker, and investigates alerts. It answers four
questions: *Are we binding at the hit ratio we planned? Which brokers drive the book and is their
pricing inside guardrails? Where is exposure concentrating? Where are actuals diverging from plan?*

The dashboard is a **single-page app with six tabs** plus a shared filter bar:
1. **Executive** (KPIs, 12-month heartbeat chart + value table, Plan vs Actual matrix, top brokers, alerts)
2. **Broker Performance** (leaderboard + broker profile modal)
3. **Exposure & Concentration** (region/coverage limit bars, top clients, Lorenz curve + Gini)
4. **Pricing & Guardrails** (what-if slider, deviation histogram, amber/red by coverage, breach list)
5. **Market Perception** (*illustrative fixture only*)
6. **Operational Workflow** (*demo-local task board only*)

## About the Design Files
The files in this bundle are **design references created in HTML** — a streaming prototype that
demonstrates the intended look, layout, and behaviour. **They are not production code to copy
directly.** The task is to **recreate these designs in the target codebase's existing environment**
(React, Vue, etc.) using its established component library, data-fetching, and routing patterns. If
no front-end exists yet, React + a charting approach of your choice is a reasonable default; the
charts here are hand-built SVG and can be reproduced with any chart library themed to the tokens
below.

Critically, this dashboard is meant to be **wired to the live ORION API** (`broker-intel-api`). The
prototype uses hardcoded fixtures that mirror the real seeded payloads. **`API-SPEC.md` in this
bundle is the authoritative data contract** — every endpoint, payload shape, formatting rule, and
the "honesty map" of which tabs are API-fed vs illustrative. Read it alongside this README: this
README covers *visual/interaction* spec, `API-SPEC.md` covers *data*.

## Fidelity
**High-fidelity.** Final colours, typography, spacing, and interactions. Recreate pixel-faithfully
using the codebase's libraries. All values come from the **Generate design system** (see Design
Tokens); do not invent new colours or type.

---

## Global Chrome (present on every tab)

### Masthead (top bar, 58px, `--color-surface`, 1px bottom rule `--color-rule`, padding 0 28px)
- **Left:** brand mark = 32×32 navy (`--color-chrome`) rounded tile (radius 9px) containing three
  rising bars (widths 3.5px; heights 8/13/18px; first two `--color-info` teal, third `--color-spot`
  coral). Beside it: "ORION" (16px/700, ink) + "Broker Relations · Centre of Excellence" (11px,
  `--color-ink-mute`); second line eyebrow "DISTRIBUTION INTELLIGENCE" (10.5px/600, uppercase,
  +0.12em tracking, ink-mute).
- **Right:** an entity-context pill (`--color-surface-sunken`, 34px, radius 10px) with a green
  status dot + "MS&AD Group · 5 reporting entities"; a **search** icon button; a **theme toggle**
  button (Moon/Sun, functional — see State); a 34×34 navy avatar tile "KI".

### Tab bar (50px, `--color-surface`, 1px bottom rule, padding 0 28px, gap 28px between items)
- Each tab = Lucide icon (16px) + label (14px/600). **Active** tab: colour `--color-ink` + a **3px
  `--color-spot` (coral) bottom border**. Inactive: `--color-ink-soft`, transparent bottom border;
  hover → `--color-ink`. Labels: Executive, Broker Performance, Exposure, Pricing & Guardrails,
  Market Perception, Operational Workflow. Icons: `LayoutDashboard, Users, Layers, Gauge, Radar,
  ListChecks`.

### Filter bar (`--color-surface-elev`, 1px bottom rule, padding 12px 28px, flex space-between)
- **Left:** a row of "control" pills (36px, 1px `--color-rule-strong` border, radius 10px,
  `--color-surface` fill; hover → `--color-surface-sunken`). Each = uppercase micro label (9.5px/600,
  +0.10em, ink-mute) + value (12.5px/600, ink) + `ChevronDown` (14px). Controls: **Entity**
  (MSRE · Global), **Coverage** (All), **Region** (All), **Tier** (All), **Period** (Aug 25 – Jul 26).
  Then a ghost **Reset** button (`RotateCcw` + "Reset").
- **Right:** an active-filter chip (removable) "MSRE · Global" (`--color-info-soft` bg,
  `--color-info-deep` text, radius 999px, with an X in a circular button) + an **as-of stamp**
  ("as of 9 Jul 2026 · 03:33 UTC", 11px, ink-mute, tabular).
- **Behaviour (to implement):** every list/aggregate GET accepts the same params
  (`entity, coverage, region, tier, period_from, period_to`, plus `limit/offset` where paginated).
  Changing any filter re-fetches the current tab with params appended. In the prototype these
  controls are **visual only** — wire them to real query params. Render active filters as removable
  chips from the response's echoed `filters`.

### Content area
`<main>`, `--color-canvas` background, padding 26px 28px 40px, each tab body capped at
`max-width:1360px; margin:0 auto`, vertical stack `gap:18px`.

---

## Screens / Views

### 1. Executive Dashboard  — `GET /api/v1/dashboard/executive`

**Layout:** 4 KPI cards (grid, 4×1fr, gap 16) → series chart card → Plan-vs-Actual card → two
side-by-side panels (top brokers | alerts), grid 2×1fr.

- **KPI card** (one template): `--color-surface`, 1px `--color-rule`, radius 14px, padding 18px 20px.
  Contains: eyebrow (icon 13px + label, 10.5px/600 uppercase +0.11em ink-mute); a row with the big
  value (34px/600, ink, letter-spacing −0.01em, tabular) and a **trend chip**; a sub caption (11.5px
  ink-mute). **Trend chip:** pill (radius 999px, 11.5px/600) with an `ArrowUpRight`/`ArrowDownRight`
  (13px) + signed % from `mom_trend`. Colour is driven by a **per-KPI "good direction"** flag —
  green (`--color-pos` on `--color-pos-soft`) when moving the good way, red
  (`--color-neg`/`--color-neg-soft`) when bad, neutral mute otherwise.
  - hit_ratio 33.3%, trend +0.9% (up=good→green), icon `Target`
  - **breach_pct 9.7%, trend −15.3% (down=good→GREEN, down-arrow)** — note the inverted semantics,
    icon `ShieldAlert`
  - plan_attainment 95.3%, trend +1.0% (up=good→green), icon `TrendingUp`
  - total_exposure $22.9B, trend +9.7% (neutral→mute), icon `Layers`
- **Series chart card:** header strip (`--color-surface-elev`, 1px bottom rule) with eyebrow "GROSS
  WRITTEN PREMIUM VS PLAN" + title "12-month heartbeat · hit ratio overlaid", and a legend (Actual
  GWP teal square, Plan GWP light-teal outlined square, Hit ratio coral line). Body = an SVG dual-axis
  chart: 12 months, **grouped bars** per month — plan (`--color-info-soft` fill, `--color-info`
  0.9px stroke) and actual (`--color-info` solid) — with a **hit-ratio line** (`--color-spot`, 2.2px,
  round joins) + dots (r3, surface fill, coral stroke) on a **secondary right axis**. Left axis =
  money in $M (ticks $0/$40/$80/$120/$160), right axis = ratio ticks (28/32/36%), gridlines
  `--color-rule`. **Below the chart** (separated by a 1px top rule) sits a **value table**: a 13-column
  grid (label col 118px + 12×1fr) with 4 rows — Month header, "Actual GWP $M", "Plan GWP $M", "Hit
  ratio" — each metric row prefixed by its colour-keyed legend swatch; cells 11.5px tabular, centred.
  This table exists specifically so exact figures are legible without reading them off the bars.
  - 12-month data (oldest→newest), actual GWP / plan GWP ($M) / hit ratio:
    Aug 105/112/33.1 · Sep 108/115/32.9 · Oct 113/118/33.5 · Nov 116/121/34.0 · Dec 120/125/32.9 ·
    Jan 113/120/32.2 · Feb 118/123/33.1 · Mar 121/126/33.8 · Apr 119/127/32.6 · May 124/128/34.2 ·
    Jun 121/129/33.0 · Jul 123/129/33.4. (In the real API, months with no data have
    `hit_ratio:null` and `"0"` money — render as an empty month.)
- **Plan vs Actual card** (this is the `/dashboard/plan-vs-actual` endpoint surfaced *inside*
  Executive): header eyebrow "PLAN VS ACTUAL" + "Entity × coverage · attainment & variance". A grid
  table, columns `172px 1.5fr 1fr 1fr 1.4fr`: **Entity · Coverage** (entity 13px/600, coverage 11px
  ink-mute) | **GWP · plan attainment** (actual value + "plan $X" + a mini attainment bar 6px, fill
  colour pos≥1.0 / warn≥0.95 / neg below, + "% attainment") | **Hit ratio Δ** (value + signed-points
  chip, green when ≥0) | **Loss ratio Δ** (value + signed-points chip, green when ≤0, em-dash when
  null) | **Flags** (red pills: "GWP < plan", "Hit < plan", "Loss > plan"; or a green "✓ on plan"
  when no flags). 8 example rows (see prototype / API-SPEC §3.6).
- **Top brokers panel:** header "TOP BROKERS BY GWP" + "View all 80 →". 5 rows, grid
  `22px 1fr auto auto`: rank, name + (tier badge · region), GWP, hit %. Rows are clickable → broker
  profile (tab 2 / modal). Hover → `--color-surface-elev`.
- **Alerts panel:** header "ALERTS" + "showing most recent · capped at 50". Rows: a **severity dot**
  (9px; red `--color-neg` / amber `--color-warn`) + message (12.5px) + a chip row (entity, coverage,
  period neutral chips + a **type chip**: guardrail=warn, aggregate limit=aux/indigo, hit vs
  plan=spot/coral). Clicking a guardrail alert should deep-link to the Guardrails tab with
  entity+coverage filters applied.

### 2. Broker Performance — `GET /api/v1/brokers` (+ `/brokers/{id}` for the modal)

**Layout:** one full-width card. Header ("BROKER LEADERBOARD" + subtitle + "80 brokers · showing
1–12"). A horizontally-scrollable table (min-width 1040px). Footer with pager ("Showing 1–12 of 80"
+ Prev/Next; server-paginated via `total` + `limit/offset`).

- **Columns** (grid `34px minmax(180px,1.5fr) 96px 116px 66px 92px 92px 84px 62px 124px`): rank ·
  broker (name 13px/600 + group subtext 10.5px ink-mute, "—" when null) · **tier badge** · home region
  · hit % (info-deep) · GWP · brokerage · **pricing deviation** (`×1.01` style; pill tinted
  `--color-warn-soft`/`--color-warn` when outside 0.90–1.20, else plain) · loss ratio (ink, or
  ink-mute "—" when null) · **12-mo sparkline** (a tiny 104×30 SVG area+line, `--color-info-soft`
  fill + `--color-info` line, no axes). Whole row clickable → profile modal; hover
  `--color-surface-elev`.
- **Tier badge ramp** (a 4-step metallic ramp built from tone tokens): PLATINUM =
  `--color-info-soft` bg / `--color-info-deep` text; GOLD = `--color-warn-soft` / `--color-warn`;
  SILVER = `--color-surface-sunken` / `--color-ink-soft`; BRONZE = `#f0e2d6` / `#8a4a24`. Pill,
  9.5px/700, +0.04em tracking.
- **Null handling:** a broker with no quotes has `hit_ratio:null` → render "—", not 0%. Same for loss
  ratio and deviation.

### 3. Broker Profile Modal — `GET /api/v1/brokers/{broker_id}`
Centred modal over a scrim (`rgba(11,34,55,.42)`), card 760px, radius 16px, shadow
`0 12px 32px rgba(11,34,55,.18)`, max-height 88vh scroll. Close on scrim click or X button.
- **Header** (surface-elev strip): name (18px/700) + tier badge + optional **NEW** chip (spot;
  driven by `is_new`); subline = broker id (mono) · "Group: {group}" (only when grouped) · region.
- **4 stat blocks:** GWP, Hit ratio (info-deep), Pricing dev., Loss ratio (each 19px/600 tabular).
- **Quotes vs binds chart** (bordered panel, 12px radius): a 520×150 SVG — grouped bars per month
  (quotes = `--color-surface-sunken` w/ rule stroke; binds = `--color-info`) + a hit-ratio line
  (`--color-spot`) on a secondary axis; legend Quotes/Binds/Hit; month labels.
- **Share of wallet** (210px side panel): a **donut** (SVG, r=15.915, `pathLength=100`,
  `stroke-dasharray="{pct}, 100"`, `--color-info` on `--color-surface-sunken`, rotated −90°) with the
  % centred + "of group GWP" + "within {group}". **`share_of_wallet` is null for ~30% of brokers
  with no group → hide the whole element and show a small "No parent group — share of wallet not
  applicable." note instead (never 0%).**
- **Coverage split** (bordered panel): horizontal GWP bars per coverage (grid
  `96px 1fr 78px 54px`): name, bar (`--color-info`), GWP value, hit % annotation.

### 4. Exposure & Concentration — `GET /api/v1/dashboard/exposure`
**Layout:** two bar-panel cards (region | coverage) → (top clients 1.5fr | Lorenz 1fr) → full-width
alerts card.
- **Named-exposure bars** (one reusable component): rows grid `96px 1fr 132px` — name · bar (track
  `--color-surface-sunken`, fill = **limit** as % of max; region bars use `--color-info`, coverage
  bars use `--color-aux`) · right value = limit (bold) + " · " + GWP (mute). Sorted by total_limit
  desc.
- **Top clients table:** rows grid `26px 88px 1fr 108px 84px` — rank · **client_ref** (mono, always
  `CL-xxxx`, privacy by design) · industry (11px, tracked) · limit · **entity chip** (colour per
  entity: MSRE=aux, AMLIN=info, MSEU=pos, MSIJ=spot, MSIGUSA=warn). Header notes "top-client-
  per-submission granularity". Top 10.
- **Lorenz curve card:** header eyebrow + a **Gini badge** (`--color-warn-soft`/`--color-warn` pill,
  "Gini 0.55"). SVG (viewBox 0 0 260 232): x & y axes (rule-strong), a dashed **equality diagonal**
  (ink-mute, 4-4 dash), the **Lorenz curve** (`--color-info`, 2.2px) with a light `--color-info-soft`
  fill under it; x-axis labels "0% … clients 100%". Caption explains the Gini. (Real `lorenz` array is
  ~800 pts — safe to downsample; the prototype models it as y=x^3.44.)
- **Aggregate-limit-breach alerts:** same Alert row component as Executive (type chip = aggregate
  limit / aux).

### 5. Pricing & Guardrails — `GET /api/v1/dashboard/guardrails?threshold=1.25`
**Layout:** what-if card → histogram card → (amber/red by coverage 1fr | breach list 1.25fr).
- **What-if control** (signature interaction, `--color-spot-soft` card w/ `--color-spot` border):
  header "WHAT-IF · PRICING THRESHOLD" (`SlidersHorizontal`). Body grid `1fr 340px`: left = a
  **range slider** (min 1.00, max 1.50, step 0.05, `accent-color:--color-spot`) with a threshold pill
  "×1.25" + explanatory copy ("lower band fixed at ×0.90; raising the threshold monotonically lowers
  the counts"); right = two white stat tiles — **Breached rows** and **Breached binds** (30px/600
  tabular). **Interactive:** dragging refetches with `?threshold=` and animates the counts down.
  Prototype models it as `rows ≈ round(129 · (1.25/t)^3.4)`, `binds ≈ rows·6.94`. `what_if` is null when
  no threshold param is sent.
- **Deviation histogram:** 9 fixed bands (`<0.80, 0.80–0.90, 0.90–0.95, 0.95–1.00, 1.00–1.05,
  1.05–1.10, 1.10–1.20, 1.20–1.30, ≥1.30`) as a **column chart** (flex columns, height = count/max,
  radius 5px top). Counts are **bind-weighted**. **In-band** bands (0.90–1.20) = `--color-info`;
  **out-of-band** = `--color-warn`. Count on top, label below; legend "in band / outside band".
- **Amber/red by coverage:** per coverage a **stacked bar** (amber `--color-warn` + red `--color-neg`
  segments over `--color-surface-sunken`), a subline "{amber} amber · {red} red · {binds} binds", and
  the **breach_pct** on the right (colour hot ≥15% neg / ≥9% warn / else ink-soft). Story: CYBER (~22%)
  and ENERGY (~18%) dominate.
- **Breach list table** (min-width 560px, columns `1.1fr 74px 74px 150px 78px`): entity · coverage,
  period, broker (mono), **deviation-vs-band strip** (a track with a shaded guardrail zone + a dot at
  the deviation position; dot colour warn when in-band, neg when out; label "×{dev} · band
  {low}–{high}", or "no plan" when `guardrail_low/high` null), and a breaches cell (amber "nA" +
  red "nR" pills). Newest first, capped at 100.

### 6. Market Perception — *illustrative fixture (no API)*
Top banner: `--color-warn-soft`/`--color-warn`, "Illustrative data — this view is a static fixture,
not fed by the ORION API." Then: 3 stat cards (Perception index 71/100 with a bar; Broker NPS +42
with a +6 YoY chip; Avg quote response 5.8h) → (Sentiment by relationship bars, colour by tone |
Positioning quadrant SVG scatter: x = price competitiveness, y = relationship, points coloured by
tier, quadrant midlines dashed) → (Why we win: green chips | Why we lose: red chips). All values
illustrative.

### 7. Operational Workflow — *demo-local (no API)*
Top banner: neutral surface-elev, "Demo-local task list — a lightweight relationship worklist; no
ingestion or messaging in scope." Then a **4-column kanban** (Open / In progress / Review / Done):
each column header = a status dot (mute/info/warn/pos) + label + count. **Task cards**
(`--color-surface`, 1px rule, radius 11px): title (12.5px/500) + a footer with an entity chip + a
**priority pill** (high=neg, med=warn, low=mute) on the left, and due date + a 22px navy assignee
avatar on the right. Do **not** build ingestion/messaging — out of scope.

---

## Interactions & Behavior
- **Tab switching:** clicking a tab swaps the content region (client-side route/state). Active tab
  gets the coral underline.
- **Theme toggle:** masthead Moon/Sun toggles light/dark by applying/removing a `.dark` class on a
  root ancestor (dark = deep-ocean palette; see tokens). Chrome (navy tiles/avatar) stays navy in
  both themes.
- **Broker row / top-broker row → profile modal:** opens `/brokers/{id}`; scrim + X + scrim-click to
  close.
- **What-if slider:** on input, refetch `?threshold=` and update the two counts (animated count-down
  reads well).
- **Filter bar:** on any change, refetch the current tab with query params; active filters shown as
  removable chips echoed from `filters`.
- **Alert deep-links:** guardrail alert → Guardrails tab with entity+coverage prefilled.
- **Hover states:** table rows and control pills wash to `--color-surface-elev` / `--color-surface-
  sunken`; solid buttons dim to opacity 0.9. **Focus:** 2px `--color-info` ring with a canvas offset.
- **Motion:** short and soft (≈180ms colour fades; modal/overlay ≈300ms `cubic-bezier(0.2,0.7,0.2,1)`).
  No bounce, no gradients, no glassmorphism.
- **States to design** (see API-SPEC §5): per-panel loading skeletons; empty-via-filters ("no records
  match these filters" + a 12-empty-month chart); null metrics (em-dash, hidden trend chip, hidden
  share-of-wallet); auth 401 + validation 422 rendered from RFC-7807 `title` + `errors[]`; truncation
  hints (alerts 50, breach list 100, clients 10). *The prototype implements the null-metric handling
  fully; loading/empty/error surfaces are specified but not all drawn — implement them.*

## State Management
- `activeTab` (enum of the 6 tabs) — drives content + underline.
- `theme` (light|dark) — root `.dark` class.
- `selectedBroker` (broker id | null) — profile modal open/target; fetches `/brokers/{id}`.
- `whatIf` (float 1.00–1.50) — guardrails threshold; drives `?threshold=` refetch.
- Filter state: `entity, coverage, region, tier, period_from, period_to, limit, offset` — shared across
  tabs; each change refetches the active tab.
- Data fetching: one GET per tab (see the endpoint on each screen above and in API-SPEC). Header
  `X-API-Key` required (demo key `demo-key`). Money is a **decimal string** — parse decimal-safe,
  display compact ($68.4M) with full value on hover. Ratios are floats 0–1. `null` means "no data"
  (never 0). `mom_trend` null → hide trend chip. Periods are ISO months (`"2026-07"` → "Jul 2026").

## Design Tokens (Generate design system — use these exact values)
**Surfaces:** canvas `#f4efe5` · surface `#ffffff` · surface-sunken `#efeae0` · surface-elev `#fbf8f2`.
**Ink:** ink `#0b2237` · ink-soft `#586b7c` · ink-mute `#9aa4ae`.
**Rules:** rule `#e4dccc` · rule-strong `#c9bfac`.
**Accents:** info/teal `#0e7c8c` (soft `#dceff2`, deep `#084853`) · spot/coral `#d97757` (soft
`#fae5da`, deep `#5c2e1a`).
**Status (each with a `-soft`):** pos `#1f8a5b`/`#dceedf` · neg `#c24545`/`#f5dcdc` · warn
`#b47312`/`#f3e5c8` · aux/indigo `#4a60a8`/`#dee3f2`. **Chrome (navy, both themes):** `#0b2237`.
**Dark theme (`.dark`):** canvas `#07182a` · surface `#14304b` · surface-sunken `#0e2640` · surface-
elev `#1a3d5f` · ink `#f1ece0` · ink-soft `#cdd8e5` · ink-mute `#98a6b8` · rule `#2b4f75` /
`#3e6794` · info `#39d3ba` (soft `#173e48`, deep `#b8f2e5`) · spot `#f0926e` · pos `#6eee7a` · neg
`#ff8585` · warn `#f8bd5e` · aux `#9ab1f2`.
**Type:** IBM Plex Sans (UI/display), IBM Plex Mono (client refs, broker ids, chart figures). Weights
500/600/700. Tabular numerals everywhere figures align. Eyebrow = 10.5px/600 uppercase +0.12em
ink-mute. Hero numbers 34px with −0.01em tracking. Sizes in use: 9–11px meta, 12–14px body/controls,
18–19px sub-heroes, 30–34px KPI heroes.
**Radius:** cards 14px · buttons 10px · nav/icon tiles 12px · small 6–8px · chips 999px.
**Spacing:** 4px base; card padding 18–22px; page gutters 26–28px; card gaps 16–18px.
**Elevation:** quiet — separation via 1px hairline rules, not shadow. Real shadow only on modals
(`0 12px 32px rgba(11,34,55,.18)`).
**Tier ramp / entity-chip / alert-type colour maps:** see the per-screen notes above.

## Iconography
Lucide, ~2px stroke, `currentColor`, default 18px. Names used: `LayoutDashboard, Users, Layers,
Gauge, Radar, ListChecks, Search, Moon, Sun, ChevronDown, RotateCcw, X, Check, Target, ShieldAlert,
TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, ArrowLeft, ArrowRight, Info, SlidersHorizontal`.
In your codebase, use your existing Lucide (or icon) integration — **do not** copy `orion-icons.js`
(it's an offline-CDN-free shim used only because the prototype sandbox blocks the Lucide CDN).

## Voice / copy
Calm, precise, analyst-to-professional. **Sentence case everywhere**; the only uppercase is the
tracked eyebrow labels. No emoji, no exclamation marks, no marketing verbs. Lead with the number,
then the qualifier. British-leaning spelling is acceptable ("colour", "organisation").

## Assets
No binary assets. The brand mark is CSS/HTML (three navy-tile bars). Fonts load from Google Fonts
(IBM Plex Sans/Mono) — use your codebase's font pipeline. Icons via Lucide.

## Files in this bundle
- `ORION Dashboard.dc.html` — the full design prototype (all six tabs, chrome, charts, modal). Open
  in a browser to see intended look/behaviour. It is a streaming "Design Component" — the markup lives
  between `<x-dc>…</x-dc>`, the logic in the `class Component extends DCLogic` script; **read it as a
  reference for structure, exact values, and the chart maths (the `buildChart`/`buildProfile`/
  `buildLorenz`/`buildHistogram` methods show precisely how each chart is computed).**
- `orion-icons.js` — the Lucide-path shim (reference only; use your own icon system).
- `API-SPEC.md` — **the authoritative data contract** (endpoints, payloads, formatting rules, honesty
  map, controlled vocabulary, states). This is the original backend handover; treat it as source of
  truth for all data behaviour.
- `design-system-tokens/` — the Generate token CSS (`colors/typography/spacing/theme-dark/…`) for
  convenient copy of exact values.

## Notes
- The dashboard is one product on a shared "Generate" platform; it owns its screens but inherits the
  platform's tokens/primitives. Match the token values above rather than eyeballing the screenshots.
- Tabs 5 (Market Perception) and 6 (Operational Workflow) are **illustrative/demo-local** — keep their
  "illustrative"/"demo-local" affordances until real data exists.
