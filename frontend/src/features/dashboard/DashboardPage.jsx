import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

export default function DashboardPage() {
  const { instructor } = useAuth();
  return (
    <>
      <h1>Welcome, {instructor?.display_name}</h1>
      <p>
        Start by making two <Link to="/teams">teams</Link>.
      </p>
    </>
  );
}
