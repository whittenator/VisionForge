// Shared HUD-muted chart palette (OKLCH), matching the annotator class colors
// and the experiments metric chart so visuals stay consistent across the app.
export const CHART_COLORS = [
  'oklch(0.72 0.10 82)', // amber / accent
  'oklch(0.60 0.10 155)', // green
  'oklch(0.68 0.16 20)', // red
  'oklch(0.72 0.08 230)', // blue
  'oklch(0.70 0.10 75)', // gold
  'oklch(0.65 0.10 200)', // teal
  'oklch(0.62 0.10 100)', // olive
  'oklch(0.58 0.12 310)', // violet
  'oklch(0.68 0.10 40)', // orange
  'oklch(0.60 0.08 180)', // cyan
];

export const colorAt = (i: number): string => CHART_COLORS[i % CHART_COLORS.length];
