// Formatting rules from the design handoff / API-SPEC: money is a decimal
// string (display compact, full value on hover), ratios are 0–1 floats,
// null means "no data" and renders as an em-dash — never 0.

export const DASH = '—';

export function money(value) {
  if (value == null) return DASH;
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(n)) return DASH;
  const a = Math.abs(n);
  if (a >= 1e9) return '$' + (n / 1e9).toFixed(a >= 1e10 ? 1 : 2) + 'B';
  if (a >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (a >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
  return '$' + n.toFixed(0);
}

export function pct(f, dp = 1) {
  return f == null ? DASH : (f * 100).toFixed(dp) + '%';
}

export function signPct(f, dp = 1) {
  if (f == null) return DASH;
  const v = f * 100;
  return (v >= 0 ? '+' : '') + v.toFixed(dp) + '%';
}

// Signed percentage-point delta (hit-ratio / loss-ratio variance chips).
export function signPts(f) {
  if (f == null) return DASH;
  const v = f * 100;
  return (v >= 0 ? '+' : '') + v.toFixed(1);
}

export function deviation(d) {
  return d == null ? DASH : '×' + Number(d).toFixed(2);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function periodShort(p) {  // "2026-07" -> "Jul"
  return p ? MONTHS[parseInt(p.slice(5), 10) - 1] : '';
}

export function periodLong(p) {   // "2026-07" -> "Jul 2026"
  return p ? `${periodShort(p)} ${p.slice(0, 4)}` : '';
}

export function asOf(iso) {       // -> "as of 9 Jul 2026 · 03:33 UTC"
  if (!iso) return '';
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `as of ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()} · ${hh}:${mm} UTC`;
}

export const COVERAGE_NAMES = {
  PROPERTY: 'Property', CASUALTY: 'Casualty', MARINE: 'Marine', ENERGY: 'Energy',
  CYBER: 'Cyber', DO: 'Directors & Officers', PI: 'Professional Indemnity',
  FI: 'Financial Institutions',
};

export function coverageName(code) {
  return COVERAGE_NAMES[code] || code;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
