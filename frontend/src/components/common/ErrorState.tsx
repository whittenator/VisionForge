import React from 'react';

export default function ErrorState({
  title = 'Something went wrong',
  description = 'Please try again or contact support.',
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div role="alert" className="rounded-lg border border-border bg-destructive/10 p-4 text-destructive">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 text-sm">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
