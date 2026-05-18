/**
 * Auth0 SPA SDK wrapper — exposes Svelte stores and helper functions.
 *
 * Required env vars (prefix with VITE_ for Vite):
 *   VITE_AUTH0_DOMAIN    e.g. your-tenant.us.auth0.com
 *   VITE_AUTH0_CLIENT_ID  SPA application client ID
 *   VITE_AUTH0_AUDIENCE  API identifier registered in Auth0
 *
 * If none are set the module runs in dev-bypass mode:
 * the user is treated as authenticated and no token is attached.
 */
import { writable } from 'svelte/store';
import { createAuth0Client } from '@auth0/auth0-spa-js';

const DOMAIN     = import.meta.env.VITE_AUTH0_DOMAIN    || '';
const CLIENT_ID  = import.meta.env.VITE_AUTH0_CLIENT_ID || '';
const AUDIENCE   = import.meta.env.VITE_AUTH0_AUDIENCE  || '';

const DEV_BYPASS = !DOMAIN || !CLIENT_ID;

// ── Stores ────────────────────────────────────────────────────────────────────
export const authReady       = writable(false);   // SDK initialised?
export const isAuthenticated = writable(false);
export const authUser        = writable(null);    // Auth0 user profile object

let _client = null;   // Auth0Client instance

// ── Init ──────────────────────────────────────────────────────────────────────
export async function initAuth() {
  if (DEV_BYPASS) {
    // No credentials configured — run without auth (local dev)
    isAuthenticated.set(true);
    authUser.set({ name: 'Dev User', email: 'dev@local', picture: null });
    authReady.set(true);
    return;
  }

  _client = await createAuth0Client({
    domain: DOMAIN,
    clientId: CLIENT_ID,
    authorizationParams: {
      redirect_uri: window.location.origin,
      audience: AUDIENCE,
    },
    cacheLocation: 'memory',   // never persist tokens in localStorage
    useRefreshTokens: true,
  });

  // Complete redirect callback when Auth0 returns with ?code=…&state=…
  if (
    window.location.search.includes('code=') &&
    window.location.search.includes('state=')
  ) {
    try {
      await _client.handleRedirectCallback();
    } catch (e) {
      console.error('[auth] handleRedirectCallback failed:', e);
    }
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  const authed = await _client.isAuthenticated();
  isAuthenticated.set(authed);
  if (authed) {
    authUser.set(await _client.getUser());
  }
  authReady.set(true);
}

// ── Actions ───────────────────────────────────────────────────────────────────
export function login() {
  if (DEV_BYPASS || !_client) return;
  _client.loginWithRedirect();
}

export function logout() {
  if (DEV_BYPASS || !_client) return;
  _client.logout({ logoutParams: { returnTo: window.location.origin } });
}

/**
 * Get a fresh access token to send as Bearer header.
 * Returns null in dev-bypass mode (backend also skips verification).
 */
export async function getToken() {
  if (DEV_BYPASS || !_client) return null;
  try {
    return await _client.getTokenSilently();
  } catch (e) {
    if (e.error === 'login_required' || e.error === 'consent_required') {
      isAuthenticated.set(false);
    }
    return null;
  }
}
