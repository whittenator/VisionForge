import { apiPost } from './api';

export type User = { id: string; email: string; displayName: string };
export type LoginResponse = { token: string; user: User };

export async function login(email: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse>('/auth/login', { email, password });
}

export async function logout(): Promise<void> {
  await apiPost('/auth/logout');
}
