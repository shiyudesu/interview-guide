import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

function FullPageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="h-10 w-10 animate-spin rounded-full border-3 border-slate-200 border-t-primary-500" />
    </div>
  );
}

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageLoading />;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}

export function AnonymousRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageLoading />;
  if (user) {
    const state = location.state as { from?: string } | null;
    const fallback = location.pathname === '/register' ? '/settings' : '/history';
    return <Navigate to={state?.from || fallback} replace />;
  }
  return <Outlet />;
}
