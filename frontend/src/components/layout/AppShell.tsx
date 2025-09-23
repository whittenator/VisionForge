import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 rounded bg-primary px-3 py-1.5 text-primary-foreground">Skip to content</a>
      <header role="banner" className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="container mx-auto flex items-center justify-between px-4 py-3">
          <Link to="/" className="text-xl font-semibold tracking-tight">VisionForge</Link>
          <nav className="flex items-center gap-2 text-sm">
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/projects">Projects</Link>
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/datasets">Datasets</Link>
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/experiments">Experiments</Link>
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/artifacts">Artifacts</Link>
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/admin/users">Admin</Link>
            <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/help">Help</Link>
            <button className="rounded-md px-3 py-1.5 hover:bg-muted" aria-label="Notifications">Notifications</button>
            <button className="rounded-md px-3 py-1.5 hover:bg-muted" aria-label="Search">Search</button>
            <div className="rounded-md px-3 py-1.5 hover:bg-muted">Account</div>
            {user ? (
              <button className="rounded-md px-3 py-1.5 hover:bg-muted" onClick={() => void logout()} aria-label="Logout">Logout</button>
            ) : (
              <Link className="rounded-md px-3 py-1.5 hover:bg-muted" to="/login">Login</Link>
            )}
          </nav>
        </div>
      </header>
      <main id="main" role="main" className="container mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
