// Inline Lucide icon set (24×24, 2px round strokes, currentColor) — the
// subset the dashboard uses, embedded so nothing depends on a CDN.

const PATHS = {
  Search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  Moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  Sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  ChevronDown: '<path d="m6 9 6 6 6-6"/>',
  RotateCcw: '<path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5"/>',
  X: '<path d="M18 6 6 18M6 6l12 12"/>',
  Check: '<path d="M20 6 9 17l-5-5"/>',
  Target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
  ShieldAlert: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  TrendingUp: '<path d="M22 7 13.5 15.5l-5-5L2 17"/><path d="M16 7h6v6"/>',
  TrendingDown: '<path d="M22 17 13.5 8.5l-5 5L2 7"/><path d="M16 17h6v-6"/>',
  Layers: '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
  ArrowUpRight: '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
  ArrowDownRight: '<path d="M7 7 17 17"/><path d="M8 17h9V8"/>',
  ArrowRight: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  ArrowLeft: '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
  LayoutDashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  Users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  Gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  Radar: '<circle cx="12" cy="12" r="2.5"/><circle cx="12" cy="12" r="8"/><path d="M12 12 18.4 5.6"/><path d="M12 4v2"/>',
  ListChecks: '<path d="M11 6h9M11 12h9M11 18h9"/><path d="m3 5 1.4 1.4L7 4"/><path d="m3 11 1.4 1.4L7 10"/><path d="m3 17 1.4 1.4L7 16"/>',
  Info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  SlidersHorizontal: '<path d="M21 4H14M10 4H3M21 12H12M8 12H3M21 20H16M12 20H3"/><circle cx="12" cy="4" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="16" cy="20" r="2"/>',
};

export function icon(name, size = 18) {
  const body = PATHS[name] || '<circle cx="12" cy="12" r="9"/>';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none;display:inline-block;vertical-align:-2px">${body}</svg>`;
}
