import { refreshToken as requestTokenRefresh } from './auth';
import {
  getStoredToken,
  getStoredRefreshToken,
  setStoredToken,
  clearStoredToken,
} from './token-store';

export function apiUrl(path: string) {
  const envBase = (import.meta as any).env?.VITE_API_URL;
  const runtimeBase =
    (window as any).__VF_API_URL__ ||
    (typeof localStorage !== 'undefined' ? localStorage.getItem('API_URL') : null);
  const fallbackBase = window.location.origin.replace('5173', '8000');
  const base = envBase || runtimeBase || fallbackBase;
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function handle401(): never {
  clearStoredToken();
  window.location.href = '/login';
  throw new Error('Session expired. Please log in again.');
}

// Single in-flight refresh shared by all concurrent 401s so a burst of failing
// requests triggers exactly one POST /auth/refresh (no stampede).
let refreshInFlight: Promise<boolean> | null = null;

function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const stored = getStoredRefreshToken();
      if (!stored) return false;
      try {
        const refreshed = await requestTokenRefresh(stored);
        setStoredToken(refreshed.access_token);
        return true;
      } catch (err) {
        console.warn('Token refresh failed', err);
        return false;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const doFetch = () =>
    fetch(apiUrl(path), {
      ...init,
      headers: { ...(init.headers as Record<string, string> | undefined), ...getAuthHeaders() },
    });
  let res = await doFetch();
  if (res.status === 401) {
    // Try one token refresh (never for /auth/* endpoints), then retry once.
    if (!path.startsWith('/auth') && (await refreshAccessToken())) {
      res = await doFetch();
    }
    if (res.status === 401) {
      handle401();
    }
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return res;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return (await res.json()) as T;
}

export async function apiDelete(path: string): Promise<void> {
  await apiFetch(path, { method: 'DELETE' });
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return (await res.json()) as T;
}

async function safeJson(res: Response) {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}
