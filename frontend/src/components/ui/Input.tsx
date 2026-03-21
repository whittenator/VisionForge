import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export default function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'flex h-8 w-full',
        'border border-[var(--hud-border-default)] bg-[var(--hud-inset)]',
        'px-3 py-1 text-sm text-[var(--hud-text-primary)]',
        'font-[var(--hud-font-mono)] placeholder:font-[var(--hud-font-sans)]',
        'placeholder:text-[var(--hud-text-muted)]',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--hud-accent)]',
        'focus-visible:border-[var(--hud-border-accent)]',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'transition-colors duration-100',
        className
      )}
      {...props}
    />
  );
}
