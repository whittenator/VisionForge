import * as React from 'react';
import { cn } from '@/lib/utils';

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

export default function Select({ className, children, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        'h-8 w-full',
        'border border-[var(--hud-border-default)] bg-[var(--hud-inset)]',
        'px-3 py-1 text-sm text-[var(--hud-text-primary)]',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--hud-accent)]',
        'focus-visible:border-[var(--hud-border-accent)]',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'transition-colors duration-100',
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}
