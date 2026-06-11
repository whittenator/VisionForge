import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Top-level error boundary so unhandled render errors show a recoverable
 * fallback instead of a white screen.
 *
 * NOTE: this is intentionally a class component despite the project's
 * functional-components convention — React error boundaries require
 * getDerivedStateFromError / componentDidCatch, which have no hook equivalent.
 */
export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Unhandled render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6">
          <div
            role="alert"
            className="max-w-md w-full border border-[var(--hud-danger)] border-l-2 bg-[var(--hud-danger-dim)] px-4 py-3"
          >
            <h3 className="text-sm font-semibold text-[var(--hud-danger-text)] uppercase tracking-wide">
              Something went wrong
            </h3>
            <p className="mt-1 text-xs text-[var(--hud-danger-text)] opacity-80 break-words">
              {this.state.error.message || 'An unexpected error occurred.'}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-3 inline-flex items-center h-8 px-3 text-xs font-mono font-medium text-[var(--hud-text-secondary)] border border-[var(--hud-border-strong)] hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)] transition-colors tracking-wide"
            >
              RELOAD PAGE
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
