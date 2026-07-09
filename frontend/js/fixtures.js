// Static fixtures for the two non-API tabs, per the honesty map:
// Market Perception is illustrative only; Operational Workflow is demo-local.
// Values transcribed from the design handoff prototype.

export const MARKET = {
  perception: 71,
  nps: 42,
  respHours: 5.8,
  sentiment: [
    { name: 'Granite Bay', score: 0.78, tone: 'pos' },
    { name: 'Meridian', score: 0.61, tone: 'pos' },
    { name: 'Aldgate', score: 0.55, tone: 'info' },
    { name: 'Denholm', score: 0.49, tone: 'info' },
    { name: 'Basel Re', score: 0.34, tone: 'warn' },
    { name: 'Village & Ross', score: 0.22, tone: 'neg' },
  ],
  winThemes: ['Speed of quote', 'Capacity appetite', 'Claims handling', 'Technical pricing', 'Relationship depth'],
  lossThemes: ['Price competitiveness', 'Coverage flexibility', 'Turnaround on cyber', 'Aggregate constraints'],
  quadrant: [
    { name: 'Granite Bay', x: 0.82, y: 0.74, tier: 'PLATINUM' },
    { name: 'Meridian', x: 0.64, y: 0.58, tier: 'GOLD' },
    { name: 'Aldgate', x: 0.71, y: 0.44, tier: 'PLATINUM' },
    { name: 'Basel Re', x: 0.38, y: 0.52, tier: 'GOLD' },
    { name: 'Village & Ross', x: 0.29, y: 0.26, tier: 'BRONZE' },
  ],
};

export const WORKFLOW = {
  cols: [
    { key: 'open', label: 'Open', tone: 'var(--color-ink-mute)' },
    { key: 'progress', label: 'In progress', tone: 'var(--color-info)' },
    { key: 'review', label: 'Review', tone: 'var(--color-warn)' },
    { key: 'done', label: 'Done', tone: 'var(--color-pos)' },
  ],
  tasks: [
    { col: 'open', title: 'Review AMLIN / CYBER guardrail breaches', entity: 'AMLIN', who: 'RN', due: '11 Jul', pri: 'high' },
    { col: 'open', title: 'Chase MSIJ / CASUALTY hit-ratio shortfall', entity: 'MSIJ', who: 'KT', due: '12 Jul', pri: 'high' },
    { col: 'open', title: 'Q3 broker plan submissions — reminder', entity: 'MSRE', who: 'AO', due: '15 Jul', pri: 'med' },
    { col: 'progress', title: 'Aggregate limit review — MSRE / MARINE', entity: 'MSRE', who: 'RN', due: '10 Jul', pri: 'high' },
    { col: 'progress', title: 'Onboard new broker relationships', entity: 'MSEU', who: 'KT', due: '18 Jul', pri: 'med' },
    { col: 'review', title: 'Pricing deviation memo — Energy book', entity: 'MSEU', who: 'AO', due: '09 Jul', pri: 'med' },
    { col: 'review', title: 'Reinstate pricing band exception', entity: 'AMLIN', who: 'RN', due: '09 Jul', pri: 'low' },
    { col: 'done', title: 'June actuals reconciled vs plan', entity: 'Group', who: 'AO', due: '05 Jul', pri: 'med' },
    { col: 'done', title: 'Platinum broker QBR scheduled', entity: 'Group', who: 'KT', due: '03 Jul', pri: 'low' },
  ],
};
