import React from 'react';

interface SparklinePoint {
  date: string;
  count: number;
}

interface SparklineProps {
  data: SparklinePoint[];
  height?: number;
}

/** Compact line chart for labeling velocity over time. */
export default function Sparkline({ data, height = 120 }: SparklineProps) {
  if (data.length === 0) {
    return <p className="font-mono text-xs text-[var(--hud-text-muted)]">No recent activity</p>;
  }
  const w = 500;
  const h = height;
  const pad = 8;
  const max = data.reduce((m, d) => Math.max(m, d.count), 0) || 1;
  const n = data.length;
  const x = (i: number) => (n === 1 ? w / 2 : pad + (i / (n - 1)) * (w - 2 * pad));
  const y = (v: number) => h - pad - (v / max) * (h - 2 * pad);
  const points = data.map((d, i) => `${x(i)},${y(d.count)}`).join(' ');
  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label="labeling velocity"
      >
        <polyline
          points={points}
          fill="none"
          stroke="var(--hud-accent)"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
        {data.map((d, i) => (
          <circle key={d.date} cx={x(i)} cy={y(d.count)} r={2} fill="var(--hud-accent)" />
        ))}
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[0.625rem] text-[var(--hud-text-muted)]">
        <span>{data[0].date}</span>
        <span>{total} annotations / 30d</span>
        <span>{data[data.length - 1].date}</span>
      </div>
    </div>
  );
}
