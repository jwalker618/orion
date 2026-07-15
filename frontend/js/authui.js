// Auth surfaces — vanilla port of @generate-web/auth's LoginScreen/LoginForm,
// MFAVerify/MFASetup and the DSI SessionPill, styled on the same tokens.

import { auth } from './auth.js';
import { icon } from './icons.js';
import { esc } from './format.js';

const ROLE_LABELS = {
  group_admin: 'Group admin',
  broker_relations: 'Broker relations',
  entity_underwriter: 'Entity underwriter',
  reviewer: 'Reviewer',
};

function initials(name) {
  return (name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();
}

const brandMark = `
  <div class="brand-mark" style="width:44px;height:44px;border-radius:12px;padding:10px 0" aria-hidden="true">
    <span style="height:11px"></span><span style="height:18px"></span><span style="height:25px"></span>
  </div>`;

// --- login screen -------------------------------------------------------------

export function renderLogin(root, { onSuccess }) {
  let view = 'login'; // login | mfa | forgot | reset

  function shell(inner) {
    root.innerHTML = `
      <div class="auth-screen">
        <div class="auth-card">
          <div class="auth-brand">
            ${brandMark}
            <div>
              <div style="font-size:20px;font-weight:700;letter-spacing:.02em">ORION</div>
              <div style="font-size:11.5px;color:var(--color-ink-mute)">Broker Relations · Centre of Excellence</div>
            </div>
          </div>
          ${inner}
          <div class="auth-foot">Demo access: <span class="mono">demo.user@msinternational.com</span> — see the README. Sessions idle out after 45 minutes.</div>
        </div>
      </div>`;
  }

  function errorBox(msg) {
    return msg ? `<div class="auth-error">${esc(msg)}</div>` : '';
  }

  function drawLogin(error = '') {
    view = 'login';
    shell(`
      ${errorBox(error)}
      <form id="login-form" class="auth-form">
        <label class="auth-field"><span>Email</span>
          <input name="email" type="email" autocomplete="username" required autofocus></label>
        <label class="auth-field"><span>Password</span>
          <input name="password" type="password" autocomplete="current-password" required></label>
        <button class="auth-submit" type="submit">Sign in</button>
      </form>
      <button class="link auth-alt" id="to-forgot">Forgot password?</button>`);
    root.querySelector('#login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = new FormData(e.target);
      const btn = e.target.querySelector('.auth-submit');
      btn.disabled = true; btn.textContent = 'Signing in…';
      try {
        const { mfaRequired } = await auth.login(form.get('email'), form.get('password'));
        if (mfaRequired) drawMFA();
        else onSuccess();
      } catch (err) {
        drawLogin(err.status === 401 ? 'Invalid email or password.' : (err.title || 'Sign-in failed.'));
      }
    });
    root.querySelector('#to-forgot').addEventListener('click', () => drawForgot());
  }

  function drawMFA(error = '') {
    view = 'mfa';
    shell(`
      <div class="auth-note">${icon('ShieldAlert', 15)} Two-factor authentication — enter the 6-digit code from your authenticator (or a backup code).</div>
      ${errorBox(error)}
      <form id="mfa-form" class="auth-form">
        <label class="auth-field"><span>Code</span>
          <input name="code" inputmode="numeric" autocomplete="one-time-code" minlength="6" maxlength="16" required autofocus></label>
        <button class="auth-submit" type="submit">Verify</button>
      </form>
      <button class="link auth-alt" id="back-login">Back to sign in</button>`);
    root.querySelector('#mfa-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await auth.verifyMFA(new FormData(e.target).get('code'));
        onSuccess();
      } catch {
        drawMFA('That code did not verify — try the next one.');
      }
    });
    root.querySelector('#back-login').addEventListener('click', () => drawLogin());
  }

  function drawForgot(done = false) {
    view = 'forgot';
    shell(`
      ${done ? '<div class="auth-note">If that address has an account, a reset token has been issued (demo: it lands in the server log). Paste it below.</div>' : ''}
      ${done ? '' : `
      <form id="forgot-form" class="auth-form">
        <label class="auth-field"><span>Email</span>
          <input name="email" type="email" required autofocus></label>
        <button class="auth-submit" type="submit">Request reset</button>
      </form>`}
      ${done ? `
      <form id="reset-form" class="auth-form">
        <label class="auth-field"><span>Reset token</span><input name="token" required autofocus></label>
        <label class="auth-field"><span>New password</span>
          <input name="password" type="password" minlength="8" autocomplete="new-password" required></label>
        <button class="auth-submit" type="submit">Set password</button>
      </form>` : ''}
      <button class="link auth-alt" id="back-login">Back to sign in</button>`);
    root.querySelector('#forgot-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await auth.passwordResetRequest(new FormData(e.target).get('email'));
      drawForgot(true);
    });
    root.querySelector('#reset-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = new FormData(e.target);
      try {
        await auth.passwordResetConfirm(form.get('token'), form.get('password'));
        drawLogin('Password updated — sign in with the new one.');
      } catch {
        drawForgot(true);
      }
    });
    root.querySelector('#back-login').addEventListener('click', () => drawLogin());
  }

  drawLogin();
}

// --- session pill + user menu ---------------------------------------------------

export function renderSessionPill(el, { onLogout }) {
  const user = auth.user;
  if (!user) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <button class="session-pill" id="session-pill" aria-haspopup="menu">
      <span class="avatar" style="width:26px;height:26px;font-size:10px;border-radius:8px">${esc(initials(user.display_name))}</span>
      <span class="session-meta"><strong>${esc(user.display_name || user.email)}</strong>
        <span>${esc(ROLE_LABELS[user.role] || user.role || '')}</span></span>
      <span class="session-remaining tabular" id="session-remaining"></span>
      ${icon('ChevronDown', 13)}
    </button>
    <div class="user-menu" id="user-menu" hidden></div>`;

  const menu = el.querySelector('#user-menu');
  el.querySelector('#session-pill').addEventListener('click', () => {
    if (!menu.hidden) { menu.hidden = true; return; }
    menu.innerHTML = `
      <div class="user-menu-head">
        <div style="font-weight:600">${esc(user.display_name || '')}</div>
        <div class="dim" style="font-size:11px">${esc(user.email || '')}</div>
        <div class="dim" style="font-size:11px">${esc(user.job_title || '')}${user.organisation ? ` · ${esc(user.organisation)}` : ''}</div>
        ${user.entity_scope ? `<span class="pill" style="margin-top:6px">Scoped to ${esc(user.entity_scope)}</span>` : ''}
        ${user.review ? `<span class="pill" style="margin-top:6px;background:var(--color-warn-soft);color:var(--color-warn)">Review access</span>` : ''}
      </div>
      <button class="user-menu-item" data-menu="mfa">${icon('ShieldAlert', 14)}${user.mfa_enabled ? 'MFA enabled · backup codes' : 'Set up MFA'}</button>
      <button class="user-menu-item" data-menu="logout">${icon('X', 14)}Sign out</button>`;
    menu.hidden = false;
    menu.querySelector('[data-menu="logout"]').addEventListener('click', async () => {
      await auth.logout();
      onLogout();
    });
    menu.querySelector('[data-menu="mfa"]').addEventListener('click', () => {
      menu.hidden = true;
      openMFAModal();
    });
  });
  document.addEventListener('click', (e) => {
    if (!el.contains(e.target)) menu.hidden = true;
  });
}

export function updateSessionPill(remainingMs, warning) {
  const span = document.getElementById('session-remaining');
  if (!span) return;
  if (remainingMs == null) { span.textContent = ''; return; }
  const mins = Math.floor(remainingMs / 60000);
  const secs = Math.floor((remainingMs % 60000) / 1000);
  // Show the countdown only inside the warning window — DSI-pill behaviour.
  span.textContent = warning ? `${mins}:${String(secs).padStart(2, '0')}` : '';
  span.classList.toggle('warn', Boolean(warning));
}

// --- MFA setup modal ------------------------------------------------------------

function openMFAModal() {
  const rootEl = document.getElementById('modal-root');
  const user = auth.user;
  rootEl.innerHTML = `<div class="scrim" id="mfa-scrim"><div class="modal" style="width:480px" data-stop>
    <div class="modal-head"><div style="font-size:16px;font-weight:700">Multi-factor authentication</div>
      <button class="icon-btn" id="mfa-close" aria-label="Close">${icon('X', 17)}</button></div>
    <div class="modal-body" id="mfa-body">
      ${user.mfa_enabled
        ? `<p style="margin:0;font-size:12.5px;color:var(--color-ink-soft)">MFA is enabled on this account. You can mint a fresh set of single-use backup codes (this replaces the previous set).</p>
           <button class="auth-submit" id="mfa-codes">Generate backup codes</button>`
        : `<button class="auth-submit" id="mfa-start">Generate authenticator secret</button>`}
    </div></div></div>`;
  const body = rootEl.querySelector('#mfa-body');
  rootEl.querySelector('#mfa-close').addEventListener('click', () => { rootEl.innerHTML = ''; });
  rootEl.querySelector('#mfa-scrim').addEventListener('click', (e) => {
    if (!e.target.closest('[data-stop]')) rootEl.innerHTML = '';
  });

  body.querySelector('#mfa-codes')?.addEventListener('click', async () => {
    const { codes } = await auth.mfaBackupCodes();
    body.innerHTML = `<p style="margin:0;font-size:12.5px;color:var(--color-ink-soft)">Store these single-use codes somewhere safe — they will not be shown again.</p>
      <div class="backup-codes mono">${codes.map(c => `<span>${esc(c)}</span>`).join('')}</div>`;
  });

  body.querySelector('#mfa-start')?.addEventListener('click', async () => {
    const setup = await auth.mfaSetup();
    body.innerHTML = `
      <p style="margin:0;font-size:12.5px;color:var(--color-ink-soft)">Add this secret to your authenticator app, then confirm with a code. MFA activates on the first successful verify.</p>
      <div class="panel" style="display:flex;flex-direction:column;gap:8px">
        <span class="stat-label">Secret</span><span class="mono" style="font-size:13px;word-break:break-all">${esc(setup.secret)}</span>
        <span class="stat-label">otpauth URI</span><span class="mono dim" style="font-size:10.5px;word-break:break-all">${esc(setup.otpauth_uri)}</span>
      </div>
      <form id="mfa-confirm" class="auth-form">
        <label class="auth-field"><span>Code from your app</span>
          <input name="code" inputmode="numeric" minlength="6" maxlength="8" required autofocus></label>
        <button class="auth-submit" type="submit">Verify &amp; enable</button>
      </form>
      <div id="mfa-msg"></div>`;
    body.querySelector('#mfa-confirm').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await auth.verifyMFA(new FormData(e.target).get('code'));
        await auth.reloadUser();
        body.innerHTML = `<div class="auth-note">${icon('Check', 15)} MFA is now enabled. Generate backup codes below.</div>
          <button class="auth-submit" id="mfa-codes2">Generate backup codes</button>`;
        body.querySelector('#mfa-codes2').addEventListener('click', async () => {
          const { codes } = await auth.mfaBackupCodes();
          body.innerHTML = `<p style="margin:0;font-size:12.5px;color:var(--color-ink-soft)">Store these single-use codes somewhere safe.</p>
            <div class="backup-codes mono">${codes.map(c => `<span>${esc(c)}</span>`).join('')}</div>`;
        });
      } catch {
        body.querySelector('#mfa-msg').innerHTML = '<div class="auth-error">That code did not verify.</div>';
      }
    });
  });
}
