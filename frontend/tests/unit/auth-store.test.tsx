import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';

// Stub the auth API so the store is tested in isolation from the network.
vi.mock('@/services/auth', () => ({
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(async () => {}),
}));

import * as authApi from '@/services/auth';
import { AuthProvider, useAuth } from '@/services/auth-store';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

const fakeAuthResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  user: { id: 'u1', email: 'a@b.c', displayName: 'A' },
};

describe('auth-store', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('throws when useAuth is used outside an AuthProvider', () => {
    expect(() => renderHook(() => useAuth())).toThrow(/within AuthProvider/i);
  });

  it('starts unauthenticated once storage has been restored', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
  });

  it('login populates state and persists tokens + user', async () => {
    (authApi.login as ReturnType<typeof vi.fn>).mockResolvedValue(fakeAuthResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login('a@b.c', 'pw');
    });

    expect(authApi.login).toHaveBeenCalledWith('a@b.c', 'pw');
    expect(result.current.user?.id).toBe('u1');
    expect(result.current.token).toBe('access-1');
    expect(localStorage.getItem('vf_access_token')).toBe('access-1');
    expect(localStorage.getItem('vf_refresh_token')).toBe('refresh-1');
    expect(JSON.parse(localStorage.getItem('vf_user')!).id).toBe('u1');
  });

  it('logout clears state and stored credentials', async () => {
    (authApi.login as ReturnType<typeof vi.fn>).mockResolvedValue(fakeAuthResponse);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login('a@b.c', 'pw');
    });
    await act(async () => {
      await result.current.logout();
    });

    expect(authApi.logout).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(localStorage.getItem('vf_access_token')).toBeNull();
  });

  it('restores an existing session from localStorage on mount', async () => {
    localStorage.setItem('vf_access_token', 'stored-token');
    localStorage.setItem('vf_user', JSON.stringify({ id: 'u9', email: 'x@y.z' }));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.token).toBe('stored-token');
    expect(result.current.user?.id).toBe('u9');
  });
});
