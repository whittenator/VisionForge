import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';

const NAV_LINKS = [
  { to: '/projects', label: 'Projects' },
  { to: '/datasets', label: 'Datasets' },
  { to: '/experiments', label: 'Experiments' },
  { to: '/al', label: 'Active Learning' },
  { to: '/artifacts', label: 'Artifacts' },
  { to: '/admin/users', label: 'Admin' },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  function isActive(to: string) {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 rounded bg-primary px-3 py-1.5 text-primary-foreground"
      >
        Skip to content
      </a>
      <header role="banner" className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="container mx-auto flex items-center justify-between px-4 py-3">
          <Link to="/" className="text-xl font-semibold tracking-tight">
            VisionForge
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {NAV_LINKS.map(({ to, label }) => (
              <Link
                key={to}
                className={`rounded-md px-3 py-1.5 hover:bg-muted transition-colors ${
                  isActive(to) ? 'bg-muted font-medium' : ''
                }`}
                to={to}
              >
                {label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2 text-sm">
            {user ? (
              <>
                <span className="hidden sm:inline text-muted-foreground text-xs px-2">
                  {user.email || user.username || 'Account'}
                </span>
                <button
                  className="rounded-md px-3 py-1.5 hover:bg-muted"
                  onClick={() => void logout()}
                  aria-label="Logout"
                >
                  Logout
                </button>
              </>
            ) : (
              <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/login">
                Login
              </Link>
            )}
          </div>
        </div>
      </header>
      <main id="main" role="main" className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
