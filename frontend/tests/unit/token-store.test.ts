import { describe, it, expect, beforeEach } from 'vitest';
import {
  getStoredToken,
  setStoredToken,
  clearStoredToken,
} from '@/services/token-store';

describe('token-store', () => {
  beforeEach(() => localStorage.clear());

  it('returns null when no token is stored', () => {
    expect(getStoredToken()).toBeNull();
  });

  it('round-trips the access token', () => {
    setStoredToken('abc.def.ghi');
    expect(getStoredToken()).toBe('abc.def.ghi');
    expect(localStorage.getItem('vf_access_token')).toBe('abc.def.ghi');
  });

  it('clears the access, refresh, and user keys together', () => {
    setStoredToken('tok');
    localStorage.setItem('vf_refresh_token', 'refresh');
    localStorage.setItem('vf_user', '{"id":"1"}');

    clearStoredToken();

    expect(getStoredToken()).toBeNull();
    expect(localStorage.getItem('vf_refresh_token')).toBeNull();
    expect(localStorage.getItem('vf_user')).toBeNull();
  });
});
