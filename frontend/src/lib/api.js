/**
 * Central API helper.
 * VITE_API_URL is set in production (API Gateway URL).
 * Empty in local dev — Vite proxy forwards /api/* to localhost:8000.
 */
export const API_BASE = import.meta.env.VITE_API_URL ?? '';

export function apiFetch(path, opts) {
  return fetch(`${API_BASE}${path}`, opts);
}
