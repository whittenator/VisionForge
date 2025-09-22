import React from 'react';

export default function EmptyState({
  title = 'Nothing here yet',
  description = 'Create or import items to get started.',
  children,
}: {
  title?: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div role="status" aria-live="polite" className="rounded-lg border border-dashed p-6 text-center">
      <h3 className="text-base font-medium">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      {children ? <div className="mt-3">{children}</div> : null}
    </div>
  );
}
