// Hand-built SVG chart builders — the maths follows the handoff prototype's
// buildChart / buildSpark / buildLorenz methods, generalised to live API data
// (dynamic scales, null-month gaps).

import { periodShort } from './format.js';

// Axis scale: pick a "nice" tick step so gridline labels stay round, then
// size the axis to 4 steps.
function niceStep(raw) {
  if (raw <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (raw <= m * mag) return m * mag;
  }
  return 10 * mag;
}

function moneyTick(v) {
  if (v === 0) return '$0';
  if (v >= 1e9) return '$' + +(v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + +(v / 1e6).toFixed(1) + 'M';
  return '$' + +(v / 1e3).toFixed(0) + 'K';
}

// Executive 12-month heartbeat: grouped plan/actual bars + hit-ratio line
// on a secondary axis (prototype geometry: 1000×344, L56 R54 T42 B50).
export function seriesChart(series) {
  const W = 1000, H = 344, L = 56, R = 54, T = 42, B = 50;
  const pw = W - L - R, ph = H - T - B, n = series.length, slot = pw / n;
  const gwp = series.map(d => parseFloat(d.gwp));
  const plan = series.map(d => parseFloat(d.plan_gwp));
  const hrs = series.map(d => d.hit_ratio).filter(h => h != null);
  const moneyMax = niceStep(Math.max(...gwp, ...plan, 1) * 1.02 / 4) * 4;
  const rLo = hrs.length ? Math.min(...hrs) : 0.2;
  const rHi = hrs.length ? Math.max(...hrs) : 0.5;
  const rPad = Math.max(0.015, (rHi - rLo) * 0.6);
  const rMin = Math.max(0, rLo - rPad), rMax = rHi + rPad;

  let bars = '', line = '', dots = '', xLabels = '';
  let pen = 'M';
  series.forEach((d, i) => {
    const bw = 15, gap = 6, pairW = bw * 2 + gap;
    const sx = L + i * slot + (slot - pairW) / 2;
    const planH = plan[i] / moneyMax * ph, actH = gwp[i] / moneyMax * ph;
    bars += `<rect x="${sx.toFixed(1)}" y="${(T + ph - planH).toFixed(1)}" width="${bw}" height="${planH.toFixed(1)}" rx="2" style="fill:var(--color-info-soft);stroke:var(--color-info);stroke-width:.9"></rect>`;
    bars += `<rect x="${(sx + bw + gap).toFixed(1)}" y="${(T + ph - actH).toFixed(1)}" width="${bw}" height="${actH.toFixed(1)}" rx="2" style="fill:var(--color-info)"></rect>`;
    const cx = sx + pairW / 2;
    if (d.hit_ratio == null) {
      pen = 'M';                            // gap the line across empty months
    } else {
      const cy = T + (rMax - d.hit_ratio) / (rMax - rMin) * ph;
      line += `${pen}${cx.toFixed(1)} ${cy.toFixed(1)} `;
      pen = 'L';
      dots += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3" style="fill:var(--color-surface);stroke:var(--color-spot);stroke-width:2"></circle>`;
    }
    xLabels += `<text x="${(L + i * slot + slot / 2).toFixed(1)}" y="${H - 12}" text-anchor="middle" font-size="11" style="fill:var(--color-ink-mute)">${periodShort(d.period)}</text>`;
  });

  let grid = '';
  for (let i = 0; i <= 4; i++) {
    const v = moneyMax / 4 * i;
    const y = T + ph - (v / moneyMax * ph);
    grid += `<line x1="${L}" x2="${W - R}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" style="stroke:var(--color-rule);stroke-width:1"></line>`;
    grid += `<text x="${L - 10}" y="${(y + 3.5).toFixed(1)}" text-anchor="end" font-size="10.5" style="fill:var(--color-ink-mute)">${moneyTick(v)}</text>`;
  }
  let rTicks = '';
  for (let i = 0; i <= 2; i++) {
    const v = rMin + (rMax - rMin) * (0.2 + 0.3 * i);
    const y = T + (rMax - v) / (rMax - rMin) * ph;
    rTicks += `<text x="${W - R + 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="start" font-size="10.5" style="fill:var(--color-spot)">${(v * 100).toFixed(0)}%</text>`;
  }

  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;font-family:var(--font-mono)">
    ${grid}${rTicks}${bars}
    <path d="${line.trim()}" style="fill:none;stroke:var(--color-spot);stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round"></path>
    ${dots}${xLabels}</svg>`;
}

// 104×30 leaderboard sparkline (area + line, no axes).
export function sparkline(values, w = 104, h = 30) {
  if (!values || !values.length) return '';
  const pad = 3, lo = Math.min(...values), hi = Math.max(...values), rng = (hi - lo) || 1;
  const pts = values.map((v, i) => [
    +(pad + i / (values.length - 1) * (w - pad * 2)).toFixed(1),
    +(h - pad - (v - lo) / rng * (h - pad * 2)).toFixed(1),
  ]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1]).join(' ');
  const area = `M${pts[0][0]} ${h - pad} ` + pts.map(p => `L${p[0]} ${p[1]}`).join(' ') + ` L${pts[pts.length - 1][0]} ${h - pad} Z`;
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" style="display:block">
    <path d="${area}" style="fill:var(--color-info-soft)"></path>
    <path d="${line}" style="fill:none;stroke:var(--color-info);stroke-width:1.6;stroke-linejoin:round;stroke-linecap:round"></path></svg>`;
}

// Profile modal: quotes vs binds grouped bars + hit-ratio line (520×150).
export function profileChart(monthly) {
  const W = 520, H = 150, L = 8, R = 8, T = 12, B = 24;
  const pw = W - L - R, ph = H - T - B, slot = pw / monthly.length;
  const maxQ = Math.max(...monthly.map(m => m.quotes), 1);
  const hrs = monthly.map(m => m.hit_ratio).filter(h => h != null);
  const rLo = hrs.length ? Math.min(...hrs) : 0.2, rHi = hrs.length ? Math.max(...hrs) : 0.5;
  const rPad = Math.max(0.03, (rHi - rLo) * 0.5);
  const rMin = Math.max(0, rLo - rPad), rMax = rHi + rPad;

  let bars = '', line = '', dots = '', labels = '', pen = 'M';
  monthly.forEach((d, i) => {
    const bw = 9, gap = 4, pairW = bw * 2 + gap, sx = L + i * slot + (slot - pairW) / 2;
    const qh = d.quotes / maxQ * ph, bh = d.binds / maxQ * ph;
    bars += `<rect x="${sx.toFixed(1)}" y="${(T + ph - qh).toFixed(1)}" width="${bw}" height="${qh.toFixed(1)}" rx="1.5" style="fill:var(--color-surface-sunken);stroke:var(--color-rule-strong);stroke-width:.8"></rect>`;
    bars += `<rect x="${(sx + bw + gap).toFixed(1)}" y="${(T + ph - bh).toFixed(1)}" width="${bw}" height="${bh.toFixed(1)}" rx="1.5" style="fill:var(--color-info)"></rect>`;
    const cx = sx + pairW / 2;
    if (d.hit_ratio == null) {
      pen = 'M';
    } else {
      const cy = T + (rMax - d.hit_ratio) / (rMax - rMin) * ph;
      line += `${pen}${cx.toFixed(1)} ${cy.toFixed(1)} `;
      pen = 'L';
      dots += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="2.4" style="fill:var(--color-surface);stroke:var(--color-spot);stroke-width:1.8"></circle>`;
    }
    labels += `<text x="${(L + i * slot + slot / 2).toFixed(1)}" y="145" text-anchor="middle" font-size="9" style="fill:var(--color-ink-mute)">${periodShort(d.period)}</text>`;
  });

  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;font-family:var(--font-mono)">
    ${bars}<path d="${line.trim()}" style="fill:none;stroke:var(--color-spot);stroke-width:2;stroke-linejoin:round;stroke-linecap:round"></path>${dots}${labels}</svg>`;
}

// Lorenz curve (260×232) with equality diagonal; API points downsampled.
export function lorenzChart(points) {
  const L = 42, R = 244, T = 18, B = 192;
  const sx = x => L + x * (R - L), sy = y => B - y * (B - T);
  let pts = points || [];
  if (pts.length > 80) {
    const step = (pts.length - 1) / 79;
    pts = Array.from({ length: 80 }, (_, i) => pts[Math.round(i * step)]);
  }
  if (!pts.length) pts = [{ x: 0, y: 0 }, { x: 1, y: 1 }];
  const curve = pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(' ');
  const area = `M${sx(0)} ${sy(0)} ` + curve.replace('M', 'L') + ` L${sx(1)} ${sy(0)} Z`;
  return `<svg viewBox="0 0 260 232" width="100%" style="display:block;font-family:var(--font-mono)">
    <line x1="${sx(0)}" y1="${sy(0)}" x2="${sx(1)}" y2="${sy(0)}" style="stroke:var(--color-rule-strong);stroke-width:1"></line>
    <line x1="${sx(0)}" y1="${sy(0)}" x2="${sx(0)}" y2="${sy(1)}" style="stroke:var(--color-rule-strong);stroke-width:1"></line>
    <line x1="${sx(0)}" y1="${sy(0)}" x2="${sx(1)}" y2="${sy(1)}" style="stroke:var(--color-ink-mute);stroke-width:1;stroke-dasharray:4 4"></line>
    <path d="${area}" style="fill:var(--color-info-soft);opacity:.7"></path>
    <path d="${curve}" style="fill:none;stroke:var(--color-info);stroke-width:2.2;stroke-linejoin:round"></path>
    <text x="42" y="224" font-size="8.5" style="fill:var(--color-ink-mute)">0%</text>
    <text x="244" y="224" text-anchor="end" font-size="8.5" style="fill:var(--color-ink-mute)">clients 100%</text></svg>`;
}

// Share-of-wallet donut (r=15.915 so pathLength maps to percent).
export function donut(fraction) {
  const pct = (fraction * 100).toFixed(1);
  return `<svg viewBox="0 0 36 36" width="132" height="132" style="transform:rotate(-90deg)">
    <circle cx="18" cy="18" r="15.915" style="fill:none;stroke:var(--color-surface-sunken);stroke-width:3.6"></circle>
    <circle cx="18" cy="18" r="15.915" pathLength="100" stroke-dasharray="${pct}, 100" style="fill:none;stroke:var(--color-info);stroke-width:3.6;stroke-linecap:round"></circle></svg>`;
}
