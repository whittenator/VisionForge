import React from 'react';

export interface HistBucket {
  label: string;
  value: number;
}

interface HistogramProps {
  data: HistBucket[];
  color?: string;
  height?: number;
}

/** Vertical bucketed histogram — per-image counts, bbox area, resolution. */
export default function Histogram({
  data,
  color = 'var(--hud-accent)',
  height = 120,
}: HistogramProps) {
  const max = data.reduce((m, d) => Math.max(m, d.value), 0) || 1;
  if (data.length === 0) {
    return <p className="font-mono text-xs text-[var(--hud-text-muted)]">No data</p>;
  }

  return (
    <div className="flex items-end gap-2" style={{ height: height + 28 }}>
      {data.map((d) => (
        <div key={d.label} className="flex flex-1 flex-col items-center justify-end gap-1">
          <span className="font-mono text-[0.6875rem] text-[var(--hud-text-data)]">{d.value}</span>
          <div
            className="w-full"
            style={{
              height: `${Math.max((d.value / max) * height, d.value > 0 ? 2 : 0)}px`,
              background: color,
              minHeight: d.value > 0 ? 2 : 0,
            }}
          />
          <span className="w-full truncate text-center font-mono text-[0.625rem] text-[var(--hud-text-muted)]">
            {d.label}
          </span>
        </div>
      ))}
    </div>
  );
}
