import React from 'react';
import { cn } from '@/lib/utils';

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
};

const variantStyles: Record<NonNullable<BadgeProps['variant']>, string> = {
  default: 'bg-[var(--hud-elevated)] text-[var(--hud-text-secondary)] border-[var(--hud-border-default)]',
  success: 'bg-[var(--hud-success-dim)] text-[var(--hud-success-text)] border-[var(--hud-success)]',
  warning: 'bg-[var(--hud-warning-dim)] text-[var(--hud-warning-text)] border-[var(--hud-warning)]',
  danger:  'bg-[var(--hud-danger-dim)] text-[var(--hud-danger-text)] border-[var(--hud-danger)]',
  info:    'bg-[var(--hud-info-dim)] text-[var(--hud-info-text)] border-[var(--hud-info)]',
};

export default function Badge({ variant = 'default', className = '', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center border px-1.5 py-0 text-xs font-medium tracking-wide font-mono',
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}
