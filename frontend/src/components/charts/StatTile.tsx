import React from 'react';

interface StatTileProps {
  label: string;
  value: string | number;
  sub?: string;
  tone?: 'default' | 'accent' | 'success' | 'warning' | 'danger';
}

const TONE: Record<NonNullable<StatTileProps['tone']>, string> = {
  default: 'var(--hud-text-data)',
  accent: 'var(--hud-text-accent)',
  success: 'var(--hud-success-text)',
  warning: 'var(--hud-warning-text)',
  danger: 'var(--hud-danger-text)',
};

/** Big-number metric tile in the HUD summary-chip style. */
export default function StatTile({ label, value, sub, tone = 'default' }: StatTileProps) {
  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-3 py-2.5">
      <div className="label-overline">{label}</div>
      <div className="mt-1 font-mono text-xl leading-none" style={{ color: TONE[tone] }}>
        {value}
      </div>
      {sub && (
        <div className="mt-1 font-mono text-[0.6875rem] text-[var(--hud-text-muted)]">{sub}</div>
      )}
    </div>
  );
}
