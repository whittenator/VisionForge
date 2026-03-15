import { apiUrl } from './api';

export interface User {
  id: string;
  email: string;
  displayName: string;
  name?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(apiUrl('/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Login failed with ${res.status}`);
  }
  return (await res.json()) as AuthResponse;
}

export async function signup(name: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(apiUrl('/auth/signup'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password, acceptTerms: true }),
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Signup failed with ${res.status}`);
  }
  return (await res.json()) as AuthResponse;
}

export async function logout(): Promise<void> {
  try {
    await fetch(apiUrl('/auth/logout'), { method: 'POST' });
  } catch {
    // best-effort server-side logout
  }
}

export async function refreshToken(
  refreshToken: string
): Promise<{ access_token: string; token_type: string }> {
  const res = await fetch(apiUrl('/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Token refresh failed with ${res.status}`);
  }
  return (await res.json()) as { access_token: string; token_type: string };
}

export async function getMe(token: string): Promise<User> {
  const res = await fetch(apiUrl('/auth/me'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new Error(detail?.detail || `Failed to get user with ${res.status}`);
  }
  return (await res.json()) as User;
}

async function safeJson(res: Response) {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}
