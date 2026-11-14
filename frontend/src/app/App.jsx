import { Route, Routes } from 'react-router-dom';
import Layout from '../components/Layout.jsx';
import { AuthProvider } from '../features/auth/AuthContext.jsx';
import LoginPage from '../features/auth/LoginPage.jsx';
import RequireAuth from '../features/auth/RequireAuth.jsx';
import DashboardPage from '../features/dashboard/DashboardPage.jsx';
import TeamsPage from '../features/teams/TeamsPage.jsx';
import { SettingsProvider } from './settings.jsx';

export default function App() {
  return (
    <SettingsProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="teams" element={<TeamsPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </SettingsProvider>
  );
}
