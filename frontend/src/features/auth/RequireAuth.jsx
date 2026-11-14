import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

export default function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') {
    return (
      <p className="page" role="status">
        Loading…
      </p>
    );
  }
  if (status !== 'signedIn') return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}
