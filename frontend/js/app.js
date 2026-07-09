// ORION dashboard — application shell and tab renderers.
// Visual/interaction spec: design handoff README; data contract: API-SPEC.md.

import { icon } from './icons.js';
import { get } from './api.js';
import {
  DASH, money, pct, signPct, signPts, deviation, periodShort, periodLong,
  asOf, coverageName, esc,
} from './format.js';
import { seriesChart, sparkline, profileChart, lorenzChart, donut } from './charts.js';
import { MARKET, WORKFLOW } from './fixtures.js';

const TABS = [
  { id: 'executive', label: 'Executive', icon: 'LayoutDashboard' },
  { id: 'brokers', label: 'Broker Performance', icon: 'Users' },
  { id: 'exposure', label: 'Exposure', icon: 'Layers' },
  { id: 'guardrails', label: 'Pricing & Guardrails', icon: 'Gauge' },
  { id: 'market', label: 'Market Perception', icon: 'Radar' },
  { id: 'workflow', label: 'Operational Workflow', icon: 'ListChecks' },
];

const ENTITIES = { MSRE: 'Global', AMLIN: 'UK', MSEU: 'Europe', MSIJ: 'Japan', MSIGUSA: 'North America' };
const COVERAGES = ['PROPERTY', 'CASUALTY', 'MARINE', 'ENERGY', 'CYBER', 'DO', 'PI', 'FI'];
const REGIONS = ['UK', 'Europe', 'North America', 'Japan', 'APAC', 'LATAM', 'Middle East'];
const TIERS = ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE'];
const PERIOD_PRESETS = [
  { months: 12, label: 'Last 12 months' },
  { months: 6, label: 'Last 6 months' },
  { months: 3, label: 'Last 3 months' },
  { months: 1, label: 'This month' },
];
const ALERT_TYPE = {
  guardrail_breach: { label: 'guardrail', bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)' },
  aggregate_limit_breach: { label: 'aggregate limit', bg: 'var(--color-aux-soft)', fg: 'var(--color-aux)' },
  hit_ratio_below_plan: { label: 'hit vs plan', bg: 'var(--color-spot-soft)', fg: 'var(--color-spot-deep)' },
};
const ENTITY_CHIP = {
  MSRE: ['var(--color-aux-soft)', 'var(--color-aux)'],
  AMLIN: ['var(--color-info-soft)', 'var(--color-info-deep)'],
  MSEU: ['var(--color-pos-soft)', 'var(--color-pos)'],
  MSIJ: ['var(--color-spot-soft)', 'var(--color-spot-deep)'],
  MSIGUSA: ['var(--color-warn-soft)', 'var(--color-warn)'],
};
const PAGE_SIZE = 12;

const state = {
  tab: 'executive',
  theme: localStorage.getItem('orion-theme') || 'light',
  entity: '', coverage: '', region: '', tier: '', months: 12,
  page: 0,
  whatIf: 1.25,
};

const $main = document.getElementById('main');
const $modal = document.getElementById('modal-root');

// ─── filters ────────────────────────────────────────────────────────────────

function currentPeriod(offsetMonths = 0) {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - offsetMonths);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

function filterParams() {
  const params = {};
  for (const k of ['entity', 'coverage', 'region', 'tier']) if (state[k]) params[k] = state[k];
  if (state.months !== 12) {
    params.period_from = currentPeriod(state.months - 1);
    params.period_to = currentPeriod(0);
  }
  return params;
}

function periodRangeLabel() {
  const from = currentPeriod(state.months - 1), to = currentPeriod(0);
  const shortYear = p => `${periodShort(p)} ${p.slice(2, 4)}`;
  return state.months === 1 ? shortYear(to) : `${shortYear(from)} – ${shortYear(to)}`;
}

// ─── chrome ─────────────────────────────────────────────────────────────────

function renderTabs() {
  document.getElementById('tabbar').innerHTML = TABS.map(t => `
    <button class="tab ${t.id === state.tab ? 'active' : ''}" role="tab" data-action="tab" data-tab="${t.id}">
      ${icon(t.icon, 16)}<span>${t.label}</span>
    </button>`).join('');
}

function selectCtrl(name, label, value, options) {
  const opts = options.map(o => `<option value="${o.value}" ${o.value === value ? 'selected' : ''}>${o.label}</option>`).join('');
  const shown = options.find(o => o.value === value)?.label ?? 'All';
  return `<label class="ctrl">
    <span class="ctrl-label">${label}</span>
    <span class="ctrl-value">${esc(shown)}</span>
    ${icon('ChevronDown', 14)}
    <select data-filter="${name}" aria-label="${label}">${opts}</select>
  </label>`;
}

function renderFilterBar() {
  const all = [{ value: '', label: 'All' }];
  document.getElementById('filter-controls').innerHTML = [
    selectCtrl('entity', 'Entity', state.entity,
      all.concat(Object.entries(ENTITIES).map(([code, region]) => ({ value: code, label: `${code} · ${region}` })))),
    selectCtrl('coverage', 'Coverage', state.coverage,
      all.concat(COVERAGES.map(c => ({ value: c, label: c })))),
    selectCtrl('region', 'Region', state.region,
      all.concat(REGIONS.map(r => ({ value: r, label: r })))),
    selectCtrl('tier', 'Tier', state.tier,
      all.concat(TIERS.map(t => ({ value: t, label: t })))),
    selectCtrl('months', 'Period', String(state.months),
      PERIOD_PRESETS.map(p => ({ value: String(p.months), label: p.months === 12 ? periodRangeLabel12() : p.label }))),
    `<button class="ghost-btn" data-action="reset">${icon('RotateCcw', 14)}Reset</button>`,
  ].join('');
  renderChips();
}

function periodRangeLabel12() {
  const saved = state.months;
  state.months = 12;
  const label = periodRangeLabel();
  state.months = saved;
  return label;
}

function renderChips() {
  const chips = [];
  const add = (filterName, label) => chips.push(
    `<span class="filter-chip">${esc(label)}<button data-action="clear-filter" data-filter="${filterName}" aria-label="Clear ${filterName}">${icon('X', 12)}</button></span>`);
  if (state.entity) add('entity', `${state.entity} · ${ENTITIES[state.entity]}`);
  if (state.coverage) add('coverage', state.coverage);
  if (state.region) add('region', state.region);
  if (state.tier) add('tier', state.tier);
  if (state.months !== 12) add('months', periodRangeLabel());
  document.getElementById('filter-chips').innerHTML = chips.join('');
}

function applyTheme() {
  document.documentElement.classList.toggle('dark', state.theme === 'dark');
  document.getElementById('btn-theme').innerHTML = icon(state.theme === 'dark' ? 'Sun' : 'Moon', 17);
}

function setAsOf(iso) {
  document.getElementById('as-of').textContent = asOf(iso);
}

// ─── shared fragments ───────────────────────────────────────────────────────

function cardHead(eyebrow, title, right = '') {
  return `<div class="card-head">
    <div class="card-head-stack"><span class="eyebrow">${eyebrow}</span>${title ? `<span class="card-title">${title}</span>` : ''}</div>
    ${right}</div>`;
}

function alertRow(a) {
  const t = ALERT_TYPE[a.type] || { label: a.type, bg: 'var(--color-surface-sunken)', fg: 'var(--color-ink-soft)' };
  const dot = a.severity === 'red' ? 'var(--color-neg)' : 'var(--color-warn)';
  return `<div class="alert-row hrow" data-action="alert" data-type="${a.type}" data-entity="${esc(a.entity_code || '')}" data-coverage="${esc(a.coverage || '')}">
    <span class="alert-dot" style="background:${dot}"></span>
    <div style="min-width:0">
      <span class="alert-msg">${esc(a.message)}</span>
      <div class="alert-chips">
        ${a.entity_code ? `<span class="pill">${esc(a.entity_code)}</span>` : ''}
        ${a.coverage ? `<span class="pill">${esc(a.coverage)}</span>` : ''}
        ${a.period ? `<span class="pill mute tabular">${periodLong(a.period)}</span>` : ''}
        <span class="pill" style="background:${t.bg};color:${t.fg}">${t.label}</span>
      </div>
    </div></div>`;
}

function emptyPanel(msg = 'No records match these filters.') {
  return `<div class="state-panel">${esc(msg)}</div>`;
}

function errorPanel(err) {
  const items = (err.errors || []).map(e => `<li>${esc(e)}</li>`).join('');
  return `<div class="tab-body"><div class="card"><div class="state-panel error">
    <strong>${esc(err.title || 'Something went wrong')}</strong>${items ? `<ul>${items}</ul>` : ''}
  </div></div></div>`;
}

function skeletons(n = 3) {
  return `<div class="tab-body">${'<div class="skeleton"></div>'.repeat(n)}</div>`;
}

// ─── executive ──────────────────────────────────────────────────────────────

const KPI_DEFS = [
  { key: 'hit_ratio', icon: 'Target', eyebrow: 'Group hit ratio', dir: 'up', kind: 'ratio' },
  { key: 'breach_pct', icon: 'ShieldAlert', eyebrow: 'Guardrail breach rate', dir: 'down', kind: 'ratio' },
  { key: 'plan_attainment_gwp', icon: 'TrendingUp', eyebrow: 'GWP plan attainment', dir: 'up', kind: 'ratio' },
  { key: 'total_exposure', icon: 'Layers', eyebrow: 'Total exposure (limit)', dir: 'neutral', kind: 'money' },
];

function trendChip(mom, dir) {
  if (mom == null) return '';
  const cls = dir === 'neutral' ? 'flat' : ((mom > 0) === (dir === 'up') ? 'good' : 'bad');
  return `<span class="trend ${cls}">${icon(mom >= 0 ? 'ArrowUpRight' : 'ArrowDownRight', 13)}${signPct(mom)}</span>`;
}

function kpiCards(kpis, series) {
  const sumGwp = series.reduce((s, p) => s + parseFloat(p.gwp), 0);
  const sumPlan = series.reduce((s, p) => s + parseFloat(p.plan_gwp), 0);
  const subs = {
    hit_ratio: 'bound ÷ quoted across the filter range',
    breach_pct: 'of binds outside the pricing band',
    plan_attainment_gwp: `${money(sumGwp)} of ${money(sumPlan)} plan`,
    total_exposure: 'aggregate limit in force',
  };
  return KPI_DEFS.map(def => {
    const k = kpis[def.key] || {};
    const value = def.kind === 'money' ? money(k.value) : pct(k.value);
    return `<div class="kpi">
      <span class="eyebrow">${icon(def.icon, 13)}${def.eyebrow}</span>
      <div class="kpi-row"><span class="kpi-value">${value}</span>${trendChip(k.mom_trend, def.dir)}</div>
      <div class="kpi-sub">${subs[def.key]}</div>
    </div>`;
  }).join('');
}

function valueTable(series) {
  const cell = (v, extra = '') => `<span class="vt-cell ${extra}">${v}</span>`;
  return `<div class="value-table-scroll"><div class="value-table">
    <div class="vt-row vt-head"><span class="th">Month</span>
      ${series.map(p => `<span class="vt-cell" style="font-size:10.5px;font-weight:600;color:var(--color-ink-soft)">${periodShort(p.period)}</span>`).join('')}</div>
    <div class="vt-row"><span class="vt-label"><span class="sw" style="width:10px;height:10px;border-radius:3px;background:var(--color-info);display:inline-block"></span>Actual GWP <span class="dim" style="font-weight:500">$M</span></span>
      ${series.map(p => cell(Math.round(parseFloat(p.gwp) / 1e6), 'tabular')).join('')}</div>
    <div class="vt-row"><span class="vt-label" style="color:var(--color-ink-soft)"><span style="width:10px;height:10px;border-radius:3px;background:var(--color-info-soft);border:1px solid var(--color-info);display:inline-block"></span>Plan GWP <span class="dim" style="font-weight:500">$M</span></span>
      ${series.map(p => `<span class="vt-cell tabular" style="color:var(--color-ink-soft)">${Math.round(parseFloat(p.plan_gwp) / 1e6)}</span>`).join('')}</div>
    <div class="vt-row"><span class="vt-label" style="color:var(--color-spot-deep)"><span style="width:14px;height:3px;border-radius:2px;background:var(--color-spot);display:inline-block"></span>Hit ratio</span>
      ${series.map(p => `<span class="vt-cell tabular" style="font-weight:600;color:var(--color-spot-deep)">${p.hit_ratio == null ? DASH : pct(p.hit_ratio)}</span>`).join('')}</div>
  </div></div>`;
}

const FLAG_LABELS = { GWP_BELOW_PLAN: 'GWP < plan', HIT_RATIO_BELOW_PLAN: 'Hit < plan', LOSS_RATIO_ABOVE_PLAN: 'Loss > plan' };

function varChip(value, good) {
  if (value == null) return `<span class="var-chip" style="background:var(--color-surface-sunken);color:var(--color-ink-mute)">${DASH}</span>`;
  const c = good ? ['var(--color-pos-soft)', 'var(--color-pos)'] : ['var(--color-neg-soft)', 'var(--color-neg)'];
  return `<span class="var-chip" style="background:${c[0]};color:${c[1]}">${signPts(value)}</span>`;
}

function pvaCard(pva) {
  const rows = [...pva.rows].sort((a, b) => (b.flags.length - a.flags.length) || a.entity_code.localeCompare(b.entity_code));
  const flagged = rows.filter(r => r.flags.length).length;
  const body = rows.length ? rows.map(r => {
    const att = r.plan_attainment_gwp;
    const attColor = att == null ? 'var(--color-ink-mute)'
      : att >= 1 ? 'var(--color-pos)' : att >= 0.95 ? 'var(--color-warn)' : 'var(--color-neg)';
    return `<div class="pva-grid hrow">
      <div><div style="font-size:13px;font-weight:600">${esc(r.entity_code)}</div><div style="font-size:11px;color:var(--color-ink-mute)">${esc(coverageName(r.coverage))}</div></div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;align-items:baseline;justify-content:space-between" class="tabular">
          <span style="font-size:13px;font-weight:600" title="${esc(r.actual_gwp)} ${esc(r.currency)}">${money(r.actual_gwp)}</span>
          <span style="font-size:11px;color:var(--color-ink-mute)">plan ${money(r.plan_gwp)}</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="width:${att == null ? 0 : Math.min(100, att * 100).toFixed(1)}%;background:${attColor}"></div></div>
        <span class="tabular" style="font-size:10.5px;font-weight:600;color:${attColor}">${pct(att)} attainment</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px" class="tabular">
        <span style="font-size:13px;font-weight:600">${pct(r.hit_ratio)}</span>
        ${varChip(r.hit_ratio_variance, (r.hit_ratio_variance ?? 0) >= 0)}
      </div>
      <div style="display:flex;align-items:center;gap:8px" class="tabular">
        <span style="font-size:13px;font-weight:600">${pct(r.incurred_loss_ratio)}</span>
        ${varChip(r.loss_ratio_variance, (r.loss_ratio_variance ?? 1) <= 0)}
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        ${r.flags.map(f => `<span class="flag">${FLAG_LABELS[f] || f}</span>`).join('')}
        ${r.flags.length ? '' : `<span class="onplan">${icon('Check', 13)}on plan</span>`}
      </div>
    </div>`;
  }).join('') : emptyPanel();
  return `<div class="card">
    ${cardHead('Plan vs actual', 'Entity × coverage · attainment &amp; variance',
      `<span class="card-note">no flags = on plan · ${flagged} of ${rows.length} cells flagged</span>`)}
    <div style="padding:6px 20px 14px">
      <div class="pva-grid pva-head" style="border-bottom:1px solid var(--color-rule)">
        <span>Entity · Coverage</span><span>GWP · plan attainment</span><span>Hit ratio Δ</span><span>Loss ratio Δ</span><span>Flags</span>
      </div>
      <div class="pva-body">${body}</div>
    </div></div>`;
}

function renderExecutive(exec, pva) {
  const legend = `<div class="legend">
    <span><span class="sw" style="background:var(--color-info)"></span>Actual GWP</span>
    <span><span class="sw" style="background:var(--color-info-soft);border:1px solid var(--color-info)"></span>Plan GWP</span>
    <span><span class="ln" style="background:var(--color-spot)"></span>Hit ratio</span></div>`;
  const topBrokers = exec.top_brokers.length ? exec.top_brokers.map((b, i) => `
    <div class="hrow" data-action="open-broker" data-broker="${esc(b.broker_id)}" style="display:grid;grid-template-columns:22px 1fr auto auto;gap:12px;align-items:center;padding:11px 12px;border-radius:9px;cursor:pointer">
      <span class="tabular" style="font-size:12px;font-weight:600;color:var(--color-ink-mute)">${i + 1}</span>
      <div style="min-width:0">
        <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(b.broker_name)}</div>
        <span style="display:inline-flex;align-items:center;gap:6px">${b.tier ? `<span class="tier ${esc(b.tier)}">${esc(b.tier)}</span>` : ''}</span>
      </div>
      <div style="text-align:right"><div class="tabular" style="font-size:13px;font-weight:600" title="${esc(b.gwp)}">${money(b.gwp)}</div><div style="font-size:10.5px;color:var(--color-ink-mute)">GWP</div></div>
      <div style="text-align:right;min-width:54px"><div class="tabular" style="font-size:13px;font-weight:600;color:var(--color-info-deep)">${pct(b.hit_ratio)}</div><div style="font-size:10.5px;color:var(--color-ink-mute)">hit</div></div>
    </div>`).join('') : emptyPanel();

  $main.innerHTML = `<div class="tab-body">
    <div class="grid-4">${kpiCards(exec.kpis, exec.series)}</div>
    <div class="card">
      ${cardHead('Gross written premium vs plan', '12-month heartbeat · hit ratio overlaid', legend)}
      <div class="chart-wrap">${seriesChart(exec.series)}</div>
      ${valueTable(exec.series)}
    </div>
    ${pvaCard(pva)}
    <div class="grid-2">
      <div class="card">
        ${cardHead('Top brokers by GWP', '', `<button class="link" data-action="tab" data-tab="brokers">View all →</button>`)}
        <div style="padding:6px 8px 8px">${topBrokers}</div>
      </div>
      <div class="card">
        ${cardHead('Alerts', '', `<span class="card-note">showing most recent · capped at 50</span>`)}
        <div style="padding:4px 8px 8px;max-height:340px;overflow:auto">${exec.alerts.length ? exec.alerts.map(alertRow).join('') : emptyPanel('No active alerts.')}</div>
      </div>
    </div>
  </div>`;
}

// ─── broker performance ─────────────────────────────────────────────────────

function renderBrokers(data) {
  const from = data.rows.length ? state.page * PAGE_SIZE + 1 : 0;
  const to = state.page * PAGE_SIZE + data.rows.length;
  const rows = data.rows.length ? data.rows.map((b, i) => {
    const devOut = b.avg_premium_deviation != null && (b.avg_premium_deviation < 0.90 || b.avg_premium_deviation > 1.20);
    return `<div class="lb-grid hrow" data-action="open-broker" data-broker="${esc(b.broker_id)}" style="cursor:pointer">
      <span class="tabular" style="font-size:12px;font-weight:600;color:var(--color-ink-mute);text-align:right">${state.page * PAGE_SIZE + i + 1}</span>
      <div style="min-width:0">
        <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(b.broker_name)}</div>
        <div style="font-size:10.5px;color:var(--color-ink-mute)">${esc(b.broker_group || DASH)}</div>
      </div>
      <span>${b.tier ? `<span class="tier ${esc(b.tier)}">${esc(b.tier)}</span>` : DASH}</span>
      <span style="font-size:12px;color:var(--color-ink-soft)">${esc(b.home_region || DASH)}</span>
      <span class="tabular" style="font-size:12.5px;font-weight:600;color:var(--color-info-deep);text-align:right">${pct(b.hit_ratio)}</span>
      <span class="tabular" style="font-size:12.5px;font-weight:600;text-align:right" title="${esc(b.gwp)}">${money(b.gwp)}</span>
      <span class="tabular" style="font-size:12.5px;color:var(--color-ink-soft);text-align:right" title="${esc(b.brokerage)}">${money(b.brokerage)}</span>
      <span style="justify-self:center"><span class="dev-pill ${devOut ? 'out' : ''}">${deviation(b.avg_premium_deviation)}</span></span>
      <span class="tabular" style="font-size:12.5px;text-align:right;color:${b.incurred_loss_ratio == null ? 'var(--color-ink-mute)' : 'var(--color-ink)'}">${pct(b.incurred_loss_ratio)}</span>
      <span style="justify-self:center">${sparkline(b.sparkline)}</span>
    </div>`;
  }).join('') : emptyPanel();

  $main.innerHTML = `<div class="tab-body"><div class="card">
    ${cardHead('Broker leaderboard', 'Ranked by gross written premium · click a row for the profile',
      `<span class="card-note">${data.total} brokers · showing ${from}–${to}</span>`)}
    <div class="lb-scroll"><div class="lb-min">
      <div class="lb-grid">
        <span class="th" style="text-align:right">#</span><span class="th">Broker</span><span class="th">Tier</span>
        <span class="th">Home region</span><span class="th" style="text-align:right">Hit</span>
        <span class="th" style="text-align:right">GWP</span><span class="th" style="text-align:right">Brokerage</span>
        <span class="th" style="text-align:center">Pricing</span><span class="th" style="text-align:right">Loss</span>
        <span class="th" style="text-align:center">12-mo GWP</span>
      </div>${rows}
    </div></div>
    <div class="card-foot">
      <span class="card-note" style="font-size:11.5px">Showing ${from}–${to} of ${data.total} brokers</span>
      <div style="display:flex;gap:8px">
        <button class="pager-btn" data-action="page" data-dir="-1" ${state.page === 0 ? 'disabled' : ''}>${icon('ArrowLeft', 14)}Prev</button>
        <button class="pager-btn" data-action="page" data-dir="1" ${to >= data.total ? 'disabled' : ''}>Next${icon('ArrowRight', 14)}</button>
      </div>
    </div>
  </div></div>`;
}

async function openBrokerModal(brokerId) {
  $modal.innerHTML = `<div class="scrim" data-action="close-modal"><div class="modal"><div class="state-panel">Loading broker profile…</div></div></div>`;
  let p;
  try {
    p = await get(`/brokers/${encodeURIComponent(brokerId)}`, filterParams());
  } catch (err) {
    $modal.querySelector('.modal').innerHTML = `<div class="state-panel error"><strong>${esc(err.title)}</strong></div>`;
    return;
  }
  const totals = p.monthly.reduce((acc, m) => {
    acc.gwp += parseFloat(m.gwp); acc.brokerage += parseFloat(m.brokerage);
    acc.quotes += m.quotes; acc.binds += m.binds;
    if (m.avg_premium_deviation != null && m.binds > 0) { acc.devW += m.avg_premium_deviation * m.binds; acc.devB += m.binds; }
    return acc;
  }, { gwp: 0, brokerage: 0, quotes: 0, binds: 0, devW: 0, devB: 0 });
  const hr = totals.quotes ? totals.binds / totals.quotes : null;
  const dev = totals.devB ? totals.devW / totals.devB : null;
  const covMax = Math.max(...p.coverages.map(c => parseFloat(c.gwp)), 1);

  const sow = p.share_of_wallet == null
    ? `<div style="display:flex;flex-direction:column;align-items:center;gap:6px;padding:18px 0;color:var(--color-ink-mute);text-align:center">
         ${icon('Info', 20)}<span style="font-size:11.5px">No parent group — share of wallet not applicable.</span></div>`
    : `<div style="position:relative;width:132px;height:132px">${donut(p.share_of_wallet)}
         <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">
           <span class="tabular" style="font-size:22px;font-weight:600">${pct(p.share_of_wallet)}</span>
           <span style="font-size:9.5px;color:var(--color-ink-mute)">of group GWP</span>
         </div></div>
       <span style="font-size:10.5px;color:var(--color-ink-mute);text-align:center">within ${esc(p.broker_group)}</span>`;

  $modal.innerHTML = `<div class="scrim" data-action="close-modal"><div class="modal" data-stop>
    <div class="modal-head">
      <div style="display:flex;flex-direction:column;gap:7px">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span style="font-size:18px;font-weight:700">${esc(p.broker_name)}</span>
          ${p.tier ? `<span class="tier ${esc(p.tier)}" style="font-size:10px;padding:2px 9px">${esc(p.tier)}</span>` : ''}
          ${p.is_new ? `<span class="new-chip">NEW</span>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:10px;font-size:12px;color:var(--color-ink-soft)">
          <span class="mono tabular">${esc(p.broker_id)}</span>
          ${p.broker_group ? `<span class="dim">·</span><span>Group: ${esc(p.broker_group)}</span>` : ''}
          ${p.home_region ? `<span class="dim">·</span><span>${esc(p.home_region)}</span>` : ''}
        </div>
      </div>
      <button class="icon-btn" data-action="close-modal" aria-label="Close">${icon('X', 17)}</button>
    </div>
    <div class="modal-body">
      <div class="grid-4" style="gap:12px">
        <div><div class="stat-label">GWP</div><div class="stat-value">${money(totals.gwp)}</div></div>
        <div><div class="stat-label">Hit ratio</div><div class="stat-value" style="color:var(--color-info-deep)">${pct(hr)}</div></div>
        <div><div class="stat-label">Pricing dev.</div><div class="stat-value">${deviation(dev)}</div></div>
        <div><div class="stat-label">Binds</div><div class="stat-value">${totals.binds.toLocaleString()}</div></div>
      </div>
      <div class="profile-grid">
        <div class="panel">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <span class="stat-label" style="font-size:10.5px">Quotes vs binds · 12 mo</span>
            <div style="display:flex;gap:12px;font-size:10.5px;color:var(--color-ink-soft)">
              <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:9px;height:9px;border-radius:2px;background:var(--color-surface-sunken);border:1px solid var(--color-rule-strong)"></span>Quotes</span>
              <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:9px;height:9px;border-radius:2px;background:var(--color-info)"></span>Binds</span>
              <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:12px;height:2.5px;border-radius:2px;background:var(--color-spot)"></span>Hit</span>
            </div>
          </div>
          ${profileChart(p.monthly)}
        </div>
        <div class="panel" style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px">
          <span class="stat-label" style="font-size:10.5px;align-self:flex-start">Share of wallet</span>
          ${sow}
        </div>
      </div>
      <div class="panel">
        <span class="stat-label" style="font-size:10.5px">Coverage split · GWP</span>
        <div style="display:flex;flex-direction:column;gap:11px;margin-top:12px">
          ${p.coverages.length ? p.coverages.map(c => `
            <div class="cov-row">
              <span style="font-size:12px;font-weight:500">${esc(coverageName(c.coverage))}</span>
              <div class="cov-bar"><div style="width:${(parseFloat(c.gwp) / covMax * 100).toFixed(1)}%"></div></div>
              <span class="tabular" style="font-size:12px;font-weight:600;text-align:right" title="${esc(c.gwp)}">${money(c.gwp)}</span>
              <span class="tabular dim" style="font-size:11px;text-align:right">${pct(c.hit_ratio)}</span>
            </div>`).join('') : emptyPanel('No submissions in range.')}
        </div>
      </div>
    </div>
  </div></div>`;
}

// ─── exposure ───────────────────────────────────────────────────────────────

function expBars(rows, color) {
  if (!rows.length) return emptyPanel();
  const max = Math.max(...rows.map(r => parseFloat(r.total_limit)), 1);
  return rows.map(r => `<div class="exp-row">
    <span style="font-size:12px;font-weight:500">${esc(r.name)}</span>
    <div class="exp-bar"><div style="width:${(parseFloat(r.total_limit) / max * 100).toFixed(1)}%;background:${color}"></div></div>
    <div class="tabular" style="text-align:right"><span style="font-size:12.5px;font-weight:600" title="${esc(r.total_limit)}">${money(r.total_limit)}</span><span style="font-size:11px;color:var(--color-ink-mute)"> · ${money(r.gwp)}</span></div>
  </div>`).join('');
}

function renderExposure(data) {
  const clients = data.top_clients.length ? data.top_clients.map((c, i) => {
    const [bg, fg] = ENTITY_CHIP[c.entity_code] || ['var(--color-surface-sunken)', 'var(--color-ink-soft)'];
    return `<div class="client-row hrow">
      <span class="tabular" style="font-size:11.5px;color:var(--color-ink-mute);text-align:right">${i + 1}</span>
      <span class="mono" style="font-size:12.5px;font-weight:600">${esc(c.client_ref)}</span>
      <span style="font-size:11px;color:var(--color-ink-soft);letter-spacing:.02em">${esc((c.industry || DASH).replace(/_/g, ' '))}</span>
      <span class="tabular" style="font-size:12.5px;font-weight:600;text-align:right" title="${esc(c.total_limit)}">${money(c.total_limit)}</span>
      <span style="justify-self:end"><span class="pill-lg pill" style="background:${bg};color:${fg};font-weight:600">${esc(c.entity_code)}</span></span>
    </div>`;
  }).join('') : emptyPanel();

  $main.innerHTML = `<div class="tab-body">
    <div class="grid-2">
      <div class="card">
        ${cardHead('Aggregate limit by region', '', `<span class="card-note" style="font-size:10.5px">bar = limit · value = GWP</span>`)}
        <div style="padding:16px 20px;display:flex;flex-direction:column;gap:13px">${expBars(data.by_region, 'var(--color-info)')}</div>
      </div>
      <div class="card">
        ${cardHead('Aggregate limit by coverage', '', `<span class="card-note" style="font-size:10.5px">bar = limit · value = GWP</span>`)}
        <div style="padding:16px 20px;display:flex;flex-direction:column;gap:13px">${expBars(data.by_coverage, 'var(--color-aux)')}</div>
      </div>
    </div>
    <div class="grid-clients">
      <div class="card">
        ${cardHead('Top exposed clients', 'Anonymised · top-client-per-submission granularity', `<span class="card-note">top 10</span>`)}
        <div style="padding:4px 12px 10px">${clients}</div>
      </div>
      <div class="card">
        ${cardHead('Concentration · Lorenz curve', '', data.gini == null ? '' : `<span class="gini-badge">Gini ${data.gini.toFixed(2)}</span>`)}
        <div style="padding:16px 20px 10px">
          ${lorenzChart(data.lorenz)}
          <p style="margin:6px 2px 0;font-size:11px;line-height:1.5;color:var(--color-ink-mute)">${data.gini == null ? 'No client-limit data in range.' : `The curve bows below the equality diagonal — a Gini of ${data.gini.toFixed(2)} signals meaningful exposure concentration in a small set of clients.`}</p>
        </div>
      </div>
    </div>
    <div class="card">
      ${cardHead('Aggregate limit breaches', '', `<span class="card-note">${data.alerts.length} active</span>`)}
      <div style="padding:4px 8px 8px">${data.alerts.length ? data.alerts.map(alertRow).join('') : emptyPanel('No aggregate-limit breaches in range.')}</div>
    </div>
  </div>`;
}

// ─── pricing & guardrails ───────────────────────────────────────────────────

function bucketOutOfBand(b) {
  return (b.high != null && b.high <= 0.90) || (b.low != null && b.low >= 1.20);
}

function renderGuardrails(data) {
  const maxCount = Math.max(...data.histogram.map(b => b.count), 1);
  const hist = data.histogram.map(b => `
    <div class="hist-col">
      <span class="tabular" style="font-size:10.5px;font-weight:600;color:var(--color-ink-soft)">${b.count.toLocaleString()}</span>
      <div class="hist-bar" style="height:${(b.count / maxCount * 100).toFixed(1)}%;background:${bucketOutOfBand(b) ? 'var(--color-warn)' : 'var(--color-info)'}"></div>
    </div>`).join('');
  const histLabels = data.histogram.map(b => `<span>${esc(b.label)}</span>`).join('');

  const maxBreach = Math.max(...data.by_coverage.map(c => c.amber + c.red), 1);
  const covRows = data.by_coverage.length ? data.by_coverage
    .slice().sort((a, b) => (b.breach_pct ?? 0) - (a.breach_pct ?? 0))
    .map(c => {
      const pctColor = (c.breach_pct ?? 0) >= 0.15 ? 'var(--color-neg)' : (c.breach_pct ?? 0) >= 0.09 ? 'var(--color-warn)' : 'var(--color-ink-soft)';
      return `<div class="covbreach-row">
        <span style="font-size:12px;font-weight:600">${esc(c.coverage)}</span>
        <div style="display:flex;flex-direction:column;gap:4px">
          <div class="stack-bar">
            <div style="width:${(c.amber / maxBreach * 100).toFixed(1)}%;background:var(--color-warn)"></div>
            <div style="width:${(c.red / maxBreach * 100).toFixed(1)}%;background:var(--color-neg)"></div>
          </div>
          <span class="tabular" style="font-size:10px;color:var(--color-ink-mute)">${c.amber} amber · ${c.red} red · ${c.binds.toLocaleString()} binds</span>
        </div>
        <span class="tabular" style="text-align:right;font-size:12.5px;font-weight:700;color:${pctColor}">${pct(c.breach_pct)}</span>
      </div>`;
    }).join('') : emptyPanel();

  const breachRows = data.breach_list.length ? data.breach_list.map(r => {
    const hasPlan = r.guardrail_low != null;
    const lo = hasPlan ? r.guardrail_low : 0.8, hi = hasPlan ? r.guardrail_high : 1.3;
    const trackLo = lo - 0.1, trackHi = hi + 0.1;
    const posPct = v => (Math.max(0, Math.min(1, (v - trackLo) / (trackHi - trackLo))) * 100).toFixed(1) + '%';
    const inBand = hasPlan && r.avg_premium_deviation >= lo && r.avg_premium_deviation <= hi;
    return `<div class="breach-grid hrow">
      <div><div style="font-size:12.5px;font-weight:600">${esc(r.entity_code)}</div><div style="font-size:10.5px;color:var(--color-ink-mute)">${esc(r.coverage)}</div></div>
      <span class="tabular" style="font-size:11.5px;color:var(--color-ink-soft)">${periodLong(r.period)}</span>
      <span class="mono" style="font-size:11.5px;color:var(--color-ink-soft)">${esc(r.broker_id)}</span>
      <div style="display:flex;flex-direction:column;gap:4px">
        <div class="band-track">
          ${hasPlan ? `<div class="band-zone" style="left:${posPct(lo)};right:${(100 - parseFloat(posPct(hi))).toFixed(1)}%"></div>` : ''}
          <div class="band-dot" style="left:${posPct(r.avg_premium_deviation)};background:${inBand ? 'var(--color-warn)' : 'var(--color-neg)'}"></div>
        </div>
        <span class="tabular" style="font-size:10px;color:var(--color-ink-mute)">${deviation(r.avg_premium_deviation)} · band ${hasPlan ? `${r.guardrail_low.toFixed(2)}–${r.guardrail_high.toFixed(2)}` : 'no plan'}</span>
      </div>
      <div style="display:flex;gap:5px;justify-content:flex-end">
        <span class="pill" style="background:var(--color-warn-soft);color:var(--color-warn)">${r.breach_count_amber}A</span>
        <span class="pill" style="background:var(--color-neg-soft);color:var(--color-neg)">${r.breach_count_red}R</span>
      </div>
    </div>`;
  }).join('') : emptyPanel('No guardrail breaches in range.');

  $main.innerHTML = `<div class="tab-body">
    <div class="whatif-card">
      <div class="whatif-head">${icon('SlidersHorizontal', 16)}<span class="eyebrow" style="color:var(--color-spot-deep)">What-if · pricing threshold</span></div>
      <div class="whatif-body">
        <div style="display:flex;flex-direction:column;gap:14px">
          <div style="display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:12.5px;color:var(--color-spot-deep);font-weight:600">Deviation threshold</span>
            <span class="whatif-thresh" id="whatif-thresh">×${state.whatIf.toFixed(2)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:12px">
            <span class="tabular" style="font-size:11px;color:var(--color-spot-deep)">×1.00</span>
            <input type="range" min="1" max="1.5" step="0.05" value="${state.whatIf}" id="whatif-slider" aria-label="Deviation threshold">
            <span class="tabular" style="font-size:11px;color:var(--color-spot-deep)">×1.50</span>
          </div>
          <p class="whatif-copy">Counts binds whose average deviation exceeds the threshold, with the lower band fixed at ×${(data.what_if?.lower_band ?? 0.9).toFixed(2)}. Raising the threshold monotonically lowers the counts.</p>
        </div>
        <div style="display:flex;gap:14px">
          <div class="whatif-stat"><div class="stat-label">Breached rows</div><div class="whatif-num" id="whatif-rows">${(data.what_if?.breached_rows ?? 0).toLocaleString()}</div></div>
          <div class="whatif-stat"><div class="stat-label">Breached binds</div><div class="whatif-num" id="whatif-binds">${(data.what_if?.breached_binds ?? 0).toLocaleString()}</div></div>
        </div>
      </div>
    </div>
    <div class="card">
      ${cardHead('Premium deviation distribution', 'Bind-weighted · shaded band = guardrail ×0.90–×1.20',
        `<div class="legend" style="font-size:11px"><span><span class="sw" style="background:var(--color-info)"></span>in band</span><span><span class="sw" style="background:var(--color-warn)"></span>outside band</span></div>`)}
      <div style="padding:18px 22px 14px"><div class="hist">${hist}</div><div class="hist-labels">${histLabels}</div></div>
    </div>
    <div class="grid-breach">
      <div class="card">
        ${cardHead('Amber / red by coverage', '')}
        <div style="padding:16px 20px;display:flex;flex-direction:column;gap:15px">${covRows}</div>
      </div>
      <div class="card">
        ${cardHead('Breach list', '', `<span class="card-note">newest first · capped at 100</span>`)}
        <div style="overflow-x:auto"><div style="min-width:560px">
          <div class="breach-grid">
            <span class="th" style="font-size:9px">Entity · Coverage</span><span class="th" style="font-size:9px">Period</span>
            <span class="th" style="font-size:9px">Broker</span><span class="th" style="font-size:9px">Deviation vs band</span>
            <span class="th" style="font-size:9px;text-align:right">Breaches</span>
          </div>
          <div style="max-height:430px;overflow-y:auto">${breachRows}</div>
        </div></div>
      </div>
    </div>
  </div>`;

  const slider = document.getElementById('whatif-slider');
  let debounce;
  slider.addEventListener('input', () => {
    state.whatIf = parseFloat(slider.value);
    document.getElementById('whatif-thresh').textContent = '×' + state.whatIf.toFixed(2);
    clearTimeout(debounce);
    debounce = setTimeout(async () => {
      try {
        const fresh = await get('/dashboard/guardrails', { ...filterParams(), threshold: state.whatIf });
        const rowsEl = document.getElementById('whatif-rows');
        const bindsEl = document.getElementById('whatif-binds');
        if (rowsEl && fresh.what_if) {
          rowsEl.textContent = fresh.what_if.breached_rows.toLocaleString();
          bindsEl.textContent = fresh.what_if.breached_binds.toLocaleString();
        }
      } catch { /* keep the previous counts on a failed refetch */ }
    }, 180);
  });
}

// ─── market perception (illustrative fixture) ───────────────────────────────

function renderMarket() {
  const toneColor = { pos: 'var(--color-pos)', info: 'var(--color-info)', warn: 'var(--color-warn)', neg: 'var(--color-neg)' };
  const TIER_FG = { PLATINUM: 'var(--color-info-deep)', GOLD: 'var(--color-warn)', SILVER: 'var(--color-ink-soft)', BRONZE: '#8a4a24' };
  const L = 44, R = 244, T = 16, B = 196;
  const quadrant = MARKET.quadrant.map(p => {
    const cx = (L + p.x * (R - L)).toFixed(1), cy = (B - p.y * (B - T)).toFixed(1);
    return `<circle cx="${cx}" cy="${cy}" r="6" style="fill:${TIER_FG[p.tier]};opacity:.85"></circle>
      <text x="${cx}" y="${(cy - 10)}" text-anchor="middle" font-size="8.5" style="fill:var(--color-ink-soft)">${esc(p.name)}</text>`;
  }).join('');

  $main.innerHTML = `<div class="tab-body">
    <div class="banner warn">${icon('Info', 16)}<strong>Illustrative data</strong><span>— this view is a static fixture, not fed by the ORION API.</span></div>
    <div class="grid-3">
      <div class="kpi"><span class="eyebrow">Perception index</span>
        <div style="display:flex;align-items:baseline;gap:6px;margin-top:10px"><span class="kpi-value">${MARKET.perception}</span><span style="font-size:15px;color:var(--color-ink-mute)">/ 100</span></div>
        <div style="margin-top:12px;height:8px;border-radius:999px;background:var(--color-surface-sunken);overflow:hidden"><div style="height:100%;width:${MARKET.perception}%;background:var(--color-info);border-radius:999px"></div></div>
      </div>
      <div class="kpi"><span class="eyebrow">Broker NPS</span>
        <div style="display:flex;align-items:baseline;gap:8px;margin-top:10px"><span class="kpi-value" style="color:var(--color-pos)">+${MARKET.nps}</span><span class="trend good">${icon('ArrowUpRight', 12)}+6 YoY</span></div>
        <div class="kpi-sub" style="margin-top:10px">promoters less detractors, trailing 12 mo</div>
      </div>
      <div class="kpi"><span class="eyebrow">Avg quote response</span>
        <div style="display:flex;align-items:baseline;gap:4px;margin-top:10px"><span class="kpi-value">${MARKET.respHours}</span><span style="font-size:16px;color:var(--color-ink-mute)">h</span></div>
        <div class="kpi-sub" style="margin-top:10px">median time-to-first-quote to brokers</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1.25fr 1fr;gap:16px;align-items:start">
      <div class="card">
        ${cardHead('Sentiment by relationship', '')}
        <div style="padding:16px 20px;display:flex;flex-direction:column;gap:14px">
          ${MARKET.sentiment.map(s => `<div style="display:grid;grid-template-columns:132px 1fr 40px;gap:12px;align-items:center">
            <span style="font-size:12px;font-weight:500">${esc(s.name)}</span>
            <div class="exp-bar"><div style="width:${(s.score * 100).toFixed(0)}%;background:${toneColor[s.tone]}"></div></div>
            <span class="tabular" style="font-size:12px;font-weight:600;text-align:right">${(s.score * 100).toFixed(0)}</span>
          </div>`).join('')}
        </div>
      </div>
      <div class="card">
        ${cardHead('Positioning · price vs relationship', '')}
        <div style="padding:14px 18px 10px">
          <svg viewBox="0 0 268 236" width="100%" style="display:block;font-family:var(--font-sans)">
            <line x1="44" y1="196" x2="252" y2="196" style="stroke:var(--color-rule-strong);stroke-width:1"></line>
            <line x1="44" y1="196" x2="44" y2="16" style="stroke:var(--color-rule-strong);stroke-width:1"></line>
            <line x1="148" y1="196" x2="148" y2="16" style="stroke:var(--color-rule);stroke-width:1;stroke-dasharray:3 3"></line>
            <line x1="44" y1="106" x2="252" y2="106" style="stroke:var(--color-rule);stroke-width:1;stroke-dasharray:3 3"></line>
            ${quadrant}
            <text x="148" y="216" text-anchor="middle" font-size="9" style="fill:var(--color-ink-mute)">Price competitiveness →</text>
            <text x="14" y="106" text-anchor="middle" font-size="9" transform="rotate(-90 14 106)" style="fill:var(--color-ink-mute)">Relationship →</text>
          </svg>
        </div>
      </div>
    </div>
    <div class="grid-2">
      <div class="card">
        ${cardHead(`${icon('TrendingUp', 15)}Why we win`, '')}
        <div style="padding:16px 20px;display:flex;flex-wrap:wrap;gap:8px">
          ${MARKET.winThemes.map(t => `<span style="padding:6px 12px;border-radius:999px;font-size:12px;font-weight:500;background:var(--color-pos-soft);color:var(--color-pos)">${esc(t)}</span>`).join('')}
        </div>
      </div>
      <div class="card">
        ${cardHead(`${icon('TrendingDown', 15)}Why we lose`, '')}
        <div style="padding:16px 20px;display:flex;flex-wrap:wrap;gap:8px">
          ${MARKET.lossThemes.map(t => `<span style="padding:6px 12px;border-radius:999px;font-size:12px;font-weight:500;background:var(--color-neg-soft);color:var(--color-neg)">${esc(t)}</span>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

// ─── operational workflow (demo-local) ──────────────────────────────────────

function renderWorkflow() {
  const PRI = { high: ['var(--color-neg-soft)', 'var(--color-neg)'], med: ['var(--color-warn-soft)', 'var(--color-warn)'], low: ['var(--color-surface-sunken)', 'var(--color-ink-soft)'] };
  $main.innerHTML = `<div class="tab-body">
    <div class="banner neutral">${icon('Info', 16)}<strong>Demo-local task list</strong><span>— a lightweight relationship worklist; no ingestion or messaging in scope.</span></div>
    <div class="kanban">
      ${WORKFLOW.cols.map(col => {
        const tasks = WORKFLOW.tasks.filter(t => t.col === col.key);
        return `<div class="kan-col">
          <div class="kan-head"><span class="kan-title"><span class="kan-dot" style="background:${col.tone}"></span>${col.label}</span><span class="tabular card-note">${tasks.length}</span></div>
          ${tasks.map(t => `<div class="task">
            <span class="task-title">${esc(t.title)}</span>
            <div class="task-foot">
              <div style="display:flex;align-items:center;gap:6px">
                <span class="pill pill-lg">${esc(t.entity)}</span>
                <span class="pill pill-lg" style="background:${PRI[t.pri][0]};color:${PRI[t.pri][1]}">${t.pri}</span>
              </div>
              <div style="display:flex;align-items:center;gap:8px">
                <span class="tabular" style="font-size:10.5px;color:var(--color-ink-mute)">${t.due}</span>
                <span class="task-avatar">${t.who}</span>
              </div>
            </div>
          </div>`).join('')}
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

// ─── tab loading ────────────────────────────────────────────────────────────

let loadSeq = 0;

async function loadTab() {
  renderTabs();
  renderFilterBar();
  const seq = ++loadSeq;
  const f = filterParams();
  try {
    if (state.tab === 'executive') {
      $main.innerHTML = skeletons(4);
      const [exec, pva] = await Promise.all([
        get('/dashboard/executive', f),
        get('/dashboard/plan-vs-actual', f),
      ]);
      if (seq !== loadSeq) return;
      setAsOf(exec.as_of);
      renderExecutive(exec, pva);
    } else if (state.tab === 'brokers') {
      $main.innerHTML = skeletons(1);
      const data = await get('/brokers', { ...f, limit: PAGE_SIZE, offset: state.page * PAGE_SIZE });
      if (seq !== loadSeq) return;
      setAsOf(data.as_of);
      renderBrokers(data);
    } else if (state.tab === 'exposure') {
      $main.innerHTML = skeletons(3);
      const data = await get('/dashboard/exposure', f);
      if (seq !== loadSeq) return;
      setAsOf(data.as_of);
      renderExposure(data);
    } else if (state.tab === 'guardrails') {
      $main.innerHTML = skeletons(3);
      const data = await get('/dashboard/guardrails', { ...f, threshold: state.whatIf });
      if (seq !== loadSeq) return;
      setAsOf(data.as_of);
      renderGuardrails(data);
    } else if (state.tab === 'market') {
      renderMarket();
    } else if (state.tab === 'workflow') {
      renderWorkflow();
    }
  } catch (err) {
    if (seq === loadSeq) $main.innerHTML = errorPanel(err);
  }
}

// ─── events ─────────────────────────────────────────────────────────────────

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el) {
    return;
  }
  const action = el.dataset.action;
  if (action === 'tab') {
    state.tab = el.dataset.tab;
    state.page = 0;
    loadTab();
  } else if (action === 'reset') {
    Object.assign(state, { entity: '', coverage: '', region: '', tier: '', months: 12, page: 0 });
    loadTab();
  } else if (action === 'clear-filter') {
    const f = el.dataset.filter;
    state[f === 'months' ? 'months' : f] = f === 'months' ? 12 : '';
    state.page = 0;
    loadTab();
  } else if (action === 'open-broker') {
    openBrokerModal(el.dataset.broker);
  } else if (action === 'close-modal') {
    if (e.target.closest('[data-stop]') && !e.target.closest('.icon-btn[data-action="close-modal"]')) return;
    $modal.innerHTML = '';
  } else if (action === 'page') {
    state.page = Math.max(0, state.page + parseInt(el.dataset.dir, 10));
    loadTab();
  } else if (action === 'alert') {
    // Guardrail alerts deep-link to the Guardrails tab with filters applied.
    if (el.dataset.type === 'guardrail_breach') {
      state.entity = el.dataset.entity || '';
      state.coverage = el.dataset.coverage || '';
      state.tab = 'guardrails';
      loadTab();
    }
  }
});

document.addEventListener('change', (e) => {
  const sel = e.target.closest('select[data-filter]');
  if (!sel) return;
  const f = sel.dataset.filter;
  state[f === 'months' ? 'months' : f] = f === 'months' ? parseInt(sel.value, 10) : sel.value;
  state.page = 0;
  loadTab();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') $modal.innerHTML = '';
});

document.getElementById('btn-theme').addEventListener('click', () => {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('orion-theme', state.theme);
  applyTheme();
});

// ─── boot ───────────────────────────────────────────────────────────────────

document.getElementById('btn-search').innerHTML = icon('Search', 17);
applyTheme();
loadTab();
