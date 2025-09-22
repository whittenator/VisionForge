import React from 'react';

export default function SuccessState({
  title = 'All set!',
  description = 'Your action completed successfully.',
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div role="status" aria-live="polite" className="rounded-lg border border-border bg-green-50 p-4 text-green-800">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 text-sm">{description}</p>
    </div>
  );
}
