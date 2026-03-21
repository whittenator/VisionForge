import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';

const NAV_LINKS = [
  { to: '/projects',    label: 'PROJECTS'    },
  { to: '/datasets',   label: 'DATASETS'    },
  { to: '/experiments', label: 'EXPERIMENTS' },
  { to: '/artifacts',  label: 'ARTIFACTS'   },
  { to: '/admin/users', label: 'ADMIN'       },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  function isActive(to: string) {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to);
  }

  return (
    <div className="min-h-screen bg-[var(--hud-base)] text-[var(--hud-text-primary)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] px-3 py-1.5 text-xs font-medium"
      >
        Skip to content
      </a>

      {/* Top chrome bar — brand + system status */}
      <div className="border-b border-[var(--hud-border-subtle)] bg-[var(--hud-inset)] px-4 py-1 flex items-center justify-between">
        <span className="text-[0.625rem] font-mono tracking-widest text-[var(--hud-text-muted)] uppercase">
          VISIONFORGE · CV PLATFORM
        </span>
        <span className="text-[0.625rem] font-mono text-[var(--hud-success)] tracking-wide">
          ● ONLINE
        </span>
      </div>

      {/* Main nav header */}
      <header
        role="banner"
        className="sticky top-0 z-10 border-b border-[var(--hud-border-default)] bg-[var(--hud-surface)]/95 backdrop-blur-sm"
      >
        <div className="flex items-center justify-between px-4" style={{ height: '42px' }}>
          {/* Wordmark */}
          <Link
            to="/"
            className="flex items-center gap-2 text-sm font-semibold tracking-wider text-[var(--hud-text-primary)] hover:text-[var(--hud-accent)] transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <rect x="1" y="1" width="6" height="6" stroke="currentColor" strokeWidth="1.5" />
              <rect x="9" y="1" width="6" height="6" stroke="currentColor" strokeWidth="1.5" fill="currentColor" fillOpacity="0.2" />
              <rect x="1" y="9" width="6" height="6" stroke="currentColor" strokeWidth="1.5" fill="currentColor" fillOpacity="0.2" />
              <rect x="9" y="9" width="6" height="6" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            VF
          </Link>

          {/* Nav links */}
          <nav className="flex items-center h-full" aria-label="Main navigation">
            {NAV_LINKS.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={[
                  'relative flex items-center h-full px-3.5 text-xs font-mono tracking-widest transition-colors',
                  isActive(to)
                    ? 'text-[var(--hud-accent)] after:absolute after:bottom-0 after:left-0 after:right-0 after:h-px after:bg-[var(--hud-accent)]'
                    : 'text-[var(--hud-text-muted)] hover:text-[var(--hud-text-secondary)]',
                ].join(' ')}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* User section */}
          <div className="flex items-center gap-1 text-xs">
            {user ? (
              <>
                <span className="hidden sm:inline font-mono text-[var(--hud-text-muted)] px-2 text-[0.7rem]">
                  {user.email || 'Account'}
                </span>
                <button
                  className="px-3 h-6 text-[var(--hud-text-muted)] hover:text-[var(--hud-danger-text)] font-mono text-xs tracking-wide border border-transparent hover:border-[var(--hud-danger)] hover:bg-[var(--hud-danger-dim)] transition-colors"
                  onClick={() => void logout()}
                  aria-label="Logout"
                >
                  LOGOUT
                </button>
              </>
            ) : (
              <Link
                className="px-3 h-6 flex items-center text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] font-mono text-xs tracking-wide transition-colors"
                to="/login"
              >
                LOGIN
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Page content */}
      <main id="main" role="main" className="container mx-auto px-4 py-5">
        {children}
      </main>
    </div>
  );
}
