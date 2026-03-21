import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center whitespace-nowrap',
    'text-sm font-medium tracking-wide',
    'border transition-colors duration-100',
    'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--hud-accent)]',
    'disabled:pointer-events-none disabled:opacity-40',
  ].join(' '),
  {
    variants: {
      variant: {
        default:
          'bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border-[var(--hud-accent)] hover:bg-[var(--hud-accent-hover)] hover:border-[var(--hud-accent-hover)]',
        outline:
          'bg-transparent text-[var(--hud-text-primary)] border-[var(--hud-border-strong)] hover:bg-[var(--hud-elevated)] hover:border-[var(--hud-border-accent)]',
        ghost:
          'bg-transparent text-[var(--hud-text-secondary)] border-transparent hover:bg-[var(--hud-elevated)] hover:text-[var(--hud-text-primary)]',
        danger:
          'bg-[var(--hud-danger-dim)] text-[var(--hud-danger-text)] border-[var(--hud-danger)] hover:bg-[var(--hud-danger)] hover:text-[oklch(0.10_0.008_240)]',
        success:
          'bg-[var(--hud-success-dim)] text-[var(--hud-success-text)] border-[var(--hud-success)] hover:bg-[var(--hud-success)] hover:text-[oklch(0.10_0.008_240)]',
      },
      size: {
        xs: 'h-6 px-2 text-xs',
        sm: 'h-7 px-2.5 text-xs',
        md: 'h-8 px-3 text-sm',
        lg: 'h-9 px-4 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export default React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
);
