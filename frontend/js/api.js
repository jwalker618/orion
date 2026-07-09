// Thin fetch wrapper for the ORION API. Errors are RFC-7807-style
// {type, title, detail, errors[]} and are surfaced as thrown objects the
// UI renders verbatim (API-SPEC §5).

const API_BASE = '/api/v1';

export function apiKey() {
  return localStorage.getItem('orion-api-key') || 'demo-key';
}

export async function get(path, params = {}) {
  const url = new URL(API_BASE + path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  }
  let response;
  try {
    response = await fetch(url, { headers: { 'X-API-Key': apiKey() } });
  } catch (err) {
    throw { title: 'Network error', errors: [String(err)] };
  }
  if (!response.ok) {
    let problem = { title: `HTTP ${response.status}`, errors: [] };
    try { problem = await response.json(); } catch { /* keep fallback */ }
    throw { title: problem.title || `HTTP ${response.status}`, errors: problem.errors || [] };
  }
  return response.json();
}
