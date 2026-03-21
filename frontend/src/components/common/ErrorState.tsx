import React from 'react';

export default function ErrorState({
  title = 'Something went wrong',
  description = 'Please try again or contact support.',
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      role="alert"
      className="border border-[var(--hud-danger)] border-l-2 bg-[var(--hud-danger-dim)] px-4 py-3"
    >
      <h3 className="text-sm font-semibold text-[var(--hud-danger-text)] uppercase tracking-wide">
        {title}
      </h3>
      {description && (
        <p className="mt-1 text-xs text-[var(--hud-danger-text)] opacity-80">{description}</p>
      )}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
