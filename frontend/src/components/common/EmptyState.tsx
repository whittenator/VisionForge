import React from 'react';

export default function EmptyState({
  title = 'Nothing here yet',
  description = 'Create or import items to get started.',
  children,
}: {
  title?: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="border border-dashed border-[var(--hud-border-default)] px-6 py-10 text-center"
    >
      <div className="mx-auto mb-3 h-px w-8 bg-[var(--hud-border-strong)]" />
      <h3 className="text-sm font-medium text-[var(--hud-text-secondary)] uppercase tracking-wide">
        {title}
      </h3>
      <p className="mt-1 text-xs text-[var(--hud-text-muted)]">{description}</p>
      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  );
}
