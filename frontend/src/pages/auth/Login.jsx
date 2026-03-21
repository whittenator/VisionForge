import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';

export default function LoginPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state && location.state.from && location.state.from.pathname) || '/';

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (mode === 'signup') {
        await signup(name, email, password);
      } else {
        await login(email, password);
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(err?.message || (mode === 'signup' ? 'Signup failed' : 'Login failed'));
    } finally {
      setLoading(false);
    }
  }

  function toggleMode() {
    setMode((m) => (m === 'login' ? 'signup' : 'login'));
    setError('');
  }

  const inputClass =
    'w-full h-8 border border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-3 text-sm text-[var(--hud-text-primary)] font-mono placeholder:text-[var(--hud-text-muted)] placeholder:font-sans focus:outline-none focus:ring-1 focus:ring-[var(--hud-accent)] focus:border-[var(--hud-border-accent)] transition-colors';

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="mb-6">
          <div className="text-[0.625rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase mb-2">
            {mode === 'login' ? '// AUTHENTICATION' : '// ACCOUNT CREATION'}
          </div>
          <h1 className="text-lg font-semibold tracking-wide text-[var(--hud-text-primary)]">
            {mode === 'login' ? 'Sign in to VisionForge' : 'Create your account'}
          </h1>
        </div>

        {/* Form panel */}
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          {/* Panel header rule */}
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="text-[0.6875rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase">
              {mode === 'login' ? 'Login' : 'Register'}
            </span>
          </div>

          <form onSubmit={onSubmit} className="p-4 space-y-3">
            {mode === 'signup' && (
              <div className="space-y-1">
                <label htmlFor="name" className="block text-[0.6875rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase">
                  Full Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={inputClass}
                  placeholder="Jane Smith"
                  required
                />
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="email" className="block text-[0.6875rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                placeholder="user@domain.com"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="password" className="block text-[0.6875rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <div
                role="alert"
                className="border border-[var(--hud-danger)] border-l-2 bg-[var(--hud-danger-dim)] px-3 py-2 text-xs font-mono text-[var(--hud-danger-text)]"
              >
                ERR: {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-1 w-full h-8 bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border border-[var(--hud-accent)] text-xs font-mono font-medium tracking-widest uppercase hover:bg-[var(--hud-accent-hover)] disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              {loading
                ? mode === 'signup'
                  ? 'CREATING…'
                  : 'AUTHENTICATING…'
                : mode === 'signup'
                ? 'CREATE ACCOUNT'
                : 'SIGN IN'}
            </button>
          </form>

          {/* Mode toggle */}
          <div className="border-t border-[var(--hud-border-subtle)] px-4 py-3 text-center">
            <span className="text-xs text-[var(--hud-text-muted)]">
              {mode === 'login' ? 'No account?' : 'Already registered?'}{' '}
            </span>
            <button
              type="button"
              onClick={toggleMode}
              className="text-xs text-[var(--hud-accent)] hover:underline underline-offset-2 font-mono"
            >
              {mode === 'login' ? 'Sign up →' : '← Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
