import React from 'react';

export default function Spinner({ size = 16 }: { size?: number }) {
  const border = Math.max(1, Math.floor(size / 8));
  return (
    <span
      aria-label="Loading"
      className="inline-block animate-spin rounded-full"
      style={{
        width: size,
        height: size,
        borderWidth: border,
        borderStyle: 'solid',
        borderColor: 'var(--hud-border-strong)',
        borderTopColor: 'var(--hud-accent)',
      }}
    />
  );
}
