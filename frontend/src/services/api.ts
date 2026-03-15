import { getStoredToken, clearStoredToken } from './token-store';

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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path), {
    headers: { ...getAuthHeaders() },
  });
  if (res.status === 401) {
    handle401();
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    handle401();
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    handle401();
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(apiUrl(path), {
    method: 'DELETE',
    headers: { ...getAuthHeaders() },
  });
  if (res.status === 401) {
    handle401();
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    handle401();
  }
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

async function safeJson(res: Response) {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}
