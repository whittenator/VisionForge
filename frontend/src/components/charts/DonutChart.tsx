import React from 'react';

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: DonutSegment[];
  size?: number;
  centerLabel?: string;
  centerValue?: string | number;
}

/** Donut chart built from stacked stroke-dasharray arcs. */
export default function DonutChart({
  segments,
  size = 140,
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  const stroke = 16;
  const radius = (size - stroke) / 2;
  const circ = 2 * Math.PI * radius;

  let offset = 0;
  const arcs = segments
    .filter((s) => s.value > 0)
    .map((seg) => {
      const frac = total > 0 ? seg.value / total : 0;
      const dash = frac * circ;
      const arc = (
        <circle
          key={seg.label}
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={seg.color}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={-offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      );
      offset += dash;
      return arc;
    });

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} role="img" aria-label={centerLabel || 'donut chart'}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--hud-inset)"
          strokeWidth={stroke}
        />
        {arcs}
        {(centerValue !== undefined || centerLabel) && (
          <>
            <text
              x="50%"
              y="48%"
              textAnchor="middle"
              dominantBaseline="middle"
              className="font-mono"
              style={{ fill: 'var(--hud-text-data)', fontSize: 20 }}
            >
              {centerValue}
            </text>
            {centerLabel && (
              <text
                x="50%"
                y="62%"
                textAnchor="middle"
                dominantBaseline="middle"
                style={{ fill: 'var(--hud-text-muted)', fontSize: 9, letterSpacing: '0.08em' }}
              >
                {centerLabel.toUpperCase()}
              </text>
            )}
          </>
        )}
      </svg>
      <div className="space-y-1">
        {segments.map((seg) => (
          <div key={seg.label} className="flex items-center gap-2 font-mono text-[0.6875rem]">
            <span className="inline-block h-2.5 w-2.5" style={{ background: seg.color }} />
            <span className="text-[var(--hud-text-secondary)]">{seg.label}</span>
            <span className="ml-auto text-[var(--hud-text-data)]">{seg.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
