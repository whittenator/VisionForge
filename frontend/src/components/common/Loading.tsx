import React from 'react';
import Spinner from '@/components/ui/Spinner';

export default function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 text-xs text-[var(--hud-text-muted)] font-mono tracking-wide"
    >
      <Spinner size={14} />
      <span>{label}</span>
    </div>
  );
}
