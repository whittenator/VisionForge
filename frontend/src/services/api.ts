export function apiUrl(path: string) {
  const envBase = (import.meta as any).env?.VITE_API_URL;
  const runtimeBase = (window as any).__VF_API_URL__ || (typeof localStorage !== 'undefined' ? localStorage.getItem('API_URL') : null);
  const fallbackBase = window.location.origin.replace('5173', '8000');
  const base = envBase || runtimeBase || fallbackBase;
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
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
