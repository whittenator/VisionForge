import React from 'react';

type AlertProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: 'info' | 'success' | 'warning' | 'error';
};

export default function Alert({ variant = 'info', className = '', children, ...props }: AlertProps) {
  const variants = {
    info: 'bg-blue-50 text-blue-900 border-blue-200',
    success: 'bg-green-50 text-green-900 border-green-200',
    warning: 'bg-yellow-50 text-yellow-900 border-yellow-200',
    error: 'bg-red-50 text-red-900 border-red-200',
  } as const;
  return (
    <div className={`rounded border p-3 ${variants[variant]} ${className}`} role="status" {...props}>
      {children}
    </div>
  );
}
