import React, { createContext, useContext, useMemo, useState } from 'react';
import * as api from './auth';

type AuthState = {
  user: api.User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      async login(email: string, password: string) {
        const res = await api.login(email, password);
        setUser(res.user);
        setToken(res.token);
      },
      async logout() {
        await api.logout();
        setUser(null);
        setToken(null);
      },
    }),
    [user, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
