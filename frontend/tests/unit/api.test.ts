import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { apiUrl, apiGet, apiPost, apiDelete } from '@/services/api';
import { setStoredToken } from '@/services/token-store';

function jsonResponse(data: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 400),
    json: async () => data,
  } as Response;
}

beforeEach(() => {
  localStorage.clear();
  // jsdom's default location can't be navigated; replace it with a writable
  // stub so handle401's `location.href = '/login'` is observable and safe.
  Object.defineProperty(window, 'location', {
    value: { href: '', origin: 'http://localhost:5173' },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('apiUrl', () => {
  it('prefers an explicit runtime API base override', () => {
    // The localStorage `API_URL` override takes precedence over the
    // origin-derived fallback (used to point the SPA at a remote API).
    localStorage.setItem('API_URL', 'http://api.example');
    expect(apiUrl('/projects')).toBe('http://api.example/projects');
  });

  it('falls back to the origin with the dev port swapped 5173 -> 8000', () => {
    expect(apiUrl('/health')).toBe('http://localhost:8000/health');
  });

  it('normalises a path that is missing its leading slash', () => {
    expect(apiUrl('health')).toBe('http://localhost:8000/health');
  });
});

describe('apiGet', () => {
  it('returns parsed JSON and attaches the bearer token when present', async () => {
    setStoredToken('tok-123');
    const fetchMock = vi.fn(async () => jsonResponse({ id: '1' }));
    vi.stubGlobal('fetch', fetchMock);

    const out = await apiGet<{ id: string }>('/projects/1');
    expect(out).toEqual({ id: '1' });

    const [, opts] = fetchMock.mock.calls[0];
    expect((opts as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer tok-123',
    });
  });

  it('omits the Authorization header when no token is stored', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await apiGet('/public');
    const [, opts] = fetchMock.mock.calls[0];
    expect((opts as RequestInit).headers).not.toHaveProperty('Authorization');
  });

  it('clears the session and redirects to /login on 401', async () => {
    setStoredToken('expired');
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({}, { ok: false, status: 401 })));

    await expect(apiGet('/secure')).rejects.toThrow(/session expired/i);
    expect(localStorage.getItem('vf_access_token')).toBeNull();
    expect(window.location.href).toBe('/login');
  });

  it('throws the server-provided detail on a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'nope' }, { ok: false, status: 500 }))
    );
    await expect(apiGet('/boom')).rejects.toThrow('nope');
  });
});

describe('apiPost', () => {
  it('sends a JSON body with the correct method and content type', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ created: true }));
    vi.stubGlobal('fetch', fetchMock);

    const out = await apiPost<{ created: boolean }>('/projects', { name: 'x' });
    expect(out).toEqual({ created: true });

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(opts.method).toBe('POST');
    expect(opts.body).toBe(JSON.stringify({ name: 'x' }));
    expect(opts.headers).toMatchObject({ 'Content-Type': 'application/json' });
  });
});

describe('apiDelete', () => {
  it('resolves on success and throws on failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(null, { ok: true, status: 204 })));
    await expect(apiDelete('/projects/1')).resolves.toBeUndefined();

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'gone' }, { ok: false, status: 404 }))
    );
    await expect(apiDelete('/projects/1')).rejects.toThrow('gone');
  });
});
