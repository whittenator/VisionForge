import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';
import Loading from '@/components/common/Loading';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading)
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loading label="Loading..." />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
