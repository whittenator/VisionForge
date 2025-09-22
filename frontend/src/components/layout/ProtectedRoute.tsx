import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/services/auth-store';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
