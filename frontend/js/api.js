// Thin fetch wrapper for the ORION API. Errors are RFC-7807-style
// {type, title, detail, errors[]} and are surfaced as thrown objects the
// UI renders verbatim (API-SPEC §5).

import { auth } from './auth.js';

// Same-origin by default (FastAPI serves the frontend, or a Vercel rewrite
// proxies /api/* to the backend). For a split deployment without rewrites,
// set localStorage 'orion-api-base' to e.g. "https://<railway-app>/api/v1".
function apiBase() {
  return localStorage.getItem('orion-api-base') || '/api/v1';
}

export function apiKey() {
  return localStorage.getItem('orion-api-key') || 'demo-key';
}

export async function get(path, params = {}) {
  const url = new URL(apiBase() + path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  }
  const headers = auth.isAuthenticated()
    ? await auth.authHeader()
    : { 'X-API-Key': apiKey() };
  let response;
  try {
    response = await fetch(url, { headers });
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
