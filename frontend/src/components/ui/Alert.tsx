import React from 'react';
import { cn } from '@/lib/utils';

type AlertProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: 'info' | 'success' | 'warning' | 'error';
};

const variantStyles = {
  info:    'bg-[var(--hud-info-dim)] text-[var(--hud-info-text)] border-[var(--hud-info)] border-l-2',
  success: 'bg-[var(--hud-success-dim)] text-[var(--hud-success-text)] border-[var(--hud-success)] border-l-2',
  warning: 'bg-[var(--hud-warning-dim)] text-[var(--hud-warning-text)] border-[var(--hud-warning)] border-l-2',
  error:   'bg-[var(--hud-danger-dim)] text-[var(--hud-danger-text)] border-[var(--hud-danger)] border-l-2',
} as const;

export default function Alert({ variant = 'info', className = '', children, ...props }: AlertProps) {
  return (
    <div
      className={cn(
        'border border-[var(--hud-border-default)] px-3 py-2.5 text-sm',
        variantStyles[variant],
        className
      )}
      role="status"
      {...props}
    >
      {children}
    </div>
  );
}
