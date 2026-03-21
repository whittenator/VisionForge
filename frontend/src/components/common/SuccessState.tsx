import React from 'react';

export default function SuccessState({
  title = 'All set!',
  description = 'Your action completed successfully.',
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="border border-[var(--hud-success)] border-l-2 bg-[var(--hud-success-dim)] px-4 py-3"
    >
      <h3 className="text-sm font-semibold text-[var(--hud-success-text)] uppercase tracking-wide">
        {title}
      </h3>
      <p className="mt-1 text-xs text-[var(--hud-success-text)] opacity-80">{description}</p>
    </div>
  );
}
