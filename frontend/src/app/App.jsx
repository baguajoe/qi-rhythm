import { Route, Routes } from 'react-router-dom';
import Layout from '../components/Layout.jsx';
import { AuthProvider } from '../features/auth/AuthContext.jsx';
import DisplayPage from '../features/display/DisplayPage.jsx';
import LoginPage from '../features/auth/LoginPage.jsx';
import RequireAuth from '../features/auth/RequireAuth.jsx';
import ClassPage from '../features/dashboard/ClassPage.jsx';
import CalibrationPage from '../features/calibration/CalibrationPage.jsx';
import LibraryPage from '../features/library/LibraryPage.jsx';
import TeamsPage from '../features/teams/TeamsPage.jsx';
import { SettingsProvider } from './settings.jsx';

export default function App() {
  return (
    <SettingsProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/display/:sessionId" element={<DisplayPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<ClassPage />} />
            <Route path="teams" element={<TeamsPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="calibration" element={<CalibrationPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </SettingsProvider>
  );
}
