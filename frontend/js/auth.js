// Auth store + session guard — a vanilla-JS port of @generate-web/auth
// (authStore.ts + SessionGuard.tsx), same behaviour, no framework:
//   - access token in memory only; refresh token + user persisted
//   - boot() swaps the persisted refresh token for a fresh session
//   - rotating refresh with pre-expiry leeway on every authorised call
//   - 45-minute idle window, reset by DISCRETE interactions only
//     (mousedown/keydown/touchstart/pointerdown — not mousemove/scroll),
//     with a 5-minute warning threshold for the chrome countdown pill

const STORAGE_KEY = 'orion-auth';
const REFRESH_LEEWAY_MS = 30_000;
const IDLE_LIMIT_MS = 45 * 60 * 1000;
const WARN_THRESHOLD_MS = 5 * 60 * 1000;
const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'touchstart', 'pointerdown'];

function authBase() {
  return (localStorage.getItem('orion-api-base') || '/api/v1') + '/auth';
}

const state = {
  user: null,
  refreshToken: null,
  sessionExpiresAt: null,   // access-token expiry, ms epoch
  accessToken: null,        // memory only
  mfaChallengePending: false,
  lastActivity: Date.now(),
};

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    user: state.user,
    refreshToken: state.refreshToken,
    sessionExpiresAt: state.sessionExpiresAt,
  }));
}

function restore() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (raw) {
      state.user = raw.user;
      state.refreshToken = raw.refreshToken;
      state.sessionExpiresAt = raw.sessionExpiresAt;
    }
  } catch { /* corrupt state = signed out */ }
}

function wipe() {
  state.user = null;
  state.refreshToken = null;
  state.sessionExpiresAt = null;
  state.accessToken = null;
  state.mfaChallengePending = false;
  localStorage.removeItem(STORAGE_KEY);
}

async function post(path, body, accessToken = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(authBase() + path, {
    method: 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let problem = {};
    try { problem = await res.json(); } catch { /* keep empty */ }
    throw { status: res.status, title: problem.title || `HTTP ${res.status}`, errors: problem.errors || [] };
  }
  return res.status === 204 ? null : res.json();
}

async function fetchMe(accessToken) {
  const res = await fetch(authBase() + '/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw { status: res.status, title: 'Could not load profile' };
  return res.json();
}

function adopt(pair) {
  state.accessToken = pair.access_token;
  state.refreshToken = pair.refresh_token;
  state.sessionExpiresAt = Date.now() + pair.expires_in_seconds * 1000;
}

export const auth = {
  // --- session lifecycle -----------------------------------------------------

  async boot() {
    restore();
    if (!state.refreshToken) return false;
    try {
      adopt(await post('/refresh', { refresh_token: state.refreshToken }));
      state.user = await fetchMe(state.accessToken);
      persist();
      return true;
    } catch {
      wipe();
      return false;
    }
  },

  async login(email, password) {
    const resp = await post('/login', { email, password });
    adopt(resp);
    state.mfaChallengePending = resp.mfa_required;
    if (!resp.mfa_required) {
      state.user = await fetchMe(state.accessToken);
      persist();
    }
    return { mfaRequired: resp.mfa_required };
  },

  async verifyMFA(code) {
    await post('/mfa/verify', { code }, state.accessToken);
    state.mfaChallengePending = false;
    state.user = await fetchMe(state.accessToken);
    persist();
  },

  async refresh() {
    if (!state.refreshToken) return false;
    try {
      adopt(await post('/refresh', { refresh_token: state.refreshToken }));
      persist();
      return true;
    } catch {
      wipe();
      return false;
    }
  },

  async logout() {
    if (state.refreshToken) {
      try { await post('/logout', { refresh_token: state.refreshToken }); }
      catch { /* best effort — local wipe regardless */ }
    }
    wipe();
  },

  // --- profile / account actions ---------------------------------------------

  async reloadUser() {
    if (!state.accessToken) return;
    try { state.user = await fetchMe(state.accessToken); persist(); }
    catch { /* keep prior profile */ }
  },

  mfaSetup() { return post('/mfa/setup', undefined, state.accessToken); },
  mfaBackupCodes() { return post('/mfa/backup-codes', undefined, state.accessToken); },
  passwordResetRequest(email) { return post('/password/reset-request', { email }); },
  passwordResetConfirm(token, newPassword) {
    return post('/password/reset-confirm', { token, new_password: newPassword });
  },

  // --- selectors ---------------------------------------------------------------

  get user() { return state.user; },
  get mfaChallengePending() { return state.mfaChallengePending; },

  isAuthenticated() {
    return Boolean(
      state.user && state.accessToken && state.sessionExpiresAt &&
      !state.mfaChallengePending && state.sessionExpiresAt > Date.now(),
    );
  },

  hasPermission(perm) {
    return Boolean(state.user?.permissions?.includes(perm));
  },

  /** Authorization header for API calls, refreshing shortly before expiry. */
  async authHeader() {
    if (!state.accessToken) return {};
    if ((state.sessionExpiresAt ?? 0) - Date.now() < REFRESH_LEEWAY_MS) {
      await this.refresh();
    }
    return state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {};
  },

  // --- idle session guard --------------------------------------------------

  /**
   * Start the idle guard: any discrete interaction resets the 45-minute
   * window; the access token silently refreshes while inside it. Calls
   * onTick(remainingMs, warning) every second and onExpire() at zero.
   */
  startGuard({ onTick, onExpire }) {
    state.lastActivity = Date.now();
    const reset = () => { state.lastActivity = Date.now(); };
    for (const ev of ACTIVITY_EVENTS) document.addEventListener(ev, reset, { passive: true });

    const timer = setInterval(async () => {
      if (!this.isAuthenticated()) { onTick?.(null, false); return; }
      const remaining = IDLE_LIMIT_MS - (Date.now() - state.lastActivity);
      if (remaining <= 0) {
        clearInterval(timer);
        for (const ev of ACTIVITY_EVENTS) document.removeEventListener(ev, reset);
        await this.logout();
        onExpire?.();
        return;
      }
      // Keep the short-lived access token fresh while inside the window.
      if ((state.sessionExpiresAt ?? 0) - Date.now() < 2 * 60 * 1000) await this.refresh();
      onTick?.(remaining, remaining <= WARN_THRESHOLD_MS);
    }, 1000);
    return () => clearInterval(timer);
  },
};
