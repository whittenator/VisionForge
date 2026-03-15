import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import * as authApi from './auth';
import { getStoredToken, setStoredToken, clearStoredToken } from './token-store';

const REFRESH_TOKEN_KEY = 'vf_refresh_token';
const USER_KEY = 'vf_user';

type AuthState = {
  user: authApi.User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<authApi.User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true); // true while restoring from storage

  // Restore from localStorage on mount
  useEffect(() => {
    const storedToken = getStoredToken();
    const storedUser = localStorage.getItem(USER_KEY);
    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        clearStoredToken();
      }
    }
    setIsLoading(false);
  }, []);

  const _setAuth = useCallback((res: authApi.AuthResponse) => {
    setUser(res.user);
    setToken(res.access_token);
    setStoredToken(res.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, res.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(res.user));
  }, []);

  const _clearAuth = useCallback(() => {
    setUser(null);
    setToken(null);
    clearStoredToken();
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await authApi.login(email, password);
      _setAuth(res);
    },
    [_setAuth]
  );

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const res = await authApi.signup(name, email, password);
      _setAuth(res);
    },
    [_setAuth]
  );

  const logout = useCallback(async () => {
    await authApi.logout().catch(() => {});
    _clearAuth();
  }, [_clearAuth]);

  const value = useMemo<AuthState>(
    () => ({ user, token, isLoading, login, signup, logout }),
    [user, token, isLoading, login, signup, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

// Export the token getter for use in api.ts
export { getStoredToken };
