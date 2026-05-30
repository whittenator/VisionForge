import React from 'react';
import { colorAt } from '@/components/charts/colors';

export interface BarDatum {
  label: string;
  value: number;
  /** Override the auto color (e.g. to flag an imbalanced/empty class). */
  color?: string;
}

interface BarChartProps {
  data: BarDatum[];
  /** Optional unit suffix for the value labels. */
  unit?: string;
  maxBars?: number;
}

/** Horizontal bar chart — used for per-class instance/image counts. */
export default function BarChart({ data, unit = '', maxBars = 30 }: BarChartProps) {
  const rows = [...data].sort((a, b) => b.value - a.value).slice(0, maxBars);
  const max = rows.reduce((m, d) => Math.max(m, d.value), 0) || 1;

  if (rows.length === 0) {
    return <p className="font-mono text-xs text-[var(--hud-text-muted)]">No data</p>;
  }

  return (
    <div className="space-y-1.5">
      {rows.map((d, i) => (
        <div key={d.label} className="flex items-center gap-2">
          <span
            className="w-28 flex-shrink-0 truncate font-mono text-[0.6875rem] text-[var(--hud-text-secondary)]"
            title={d.label}
          >
            {d.label}
          </span>
          <div className="relative h-3.5 flex-1 bg-[var(--hud-inset)]">
            <div
              className="absolute inset-y-0 left-0"
              style={{ width: `${(d.value / max) * 100}%`, background: d.color || colorAt(i) }}
            />
          </div>
          <span className="w-14 flex-shrink-0 text-right font-mono text-[0.6875rem] text-[var(--hud-text-data)]">
            {d.value}
            {unit}
          </span>
        </div>
      ))}
    </div>
  );
}
