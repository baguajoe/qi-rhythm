import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken } from '../../lib/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: getToken() ? 'loading' : 'signedOut' });

  useEffect(() => {
    if (!getToken()) return;
    api('/api/auth/me')
      .then((d) => setState({ status: 'signedIn', ...d }))
      .catch(() => {
        setToken(null);
        setState({ status: 'signedOut' });
      });
  }, []);

  const finish = useCallback((d) => {
    setToken(d.access_token);
    setState({ status: 'signedIn', instructor: d.instructor, organization: d.organization });
  }, []);

  const login = useCallback(
    async (email, password) =>
      finish(await api('/api/auth/login', { method: 'POST', body: { email, password } })),
    [finish],
  );
  const register = useCallback(
    async (form) => finish(await api('/api/auth/register', { method: 'POST', body: form })),
    [finish],
  );
  const logout = useCallback(() => {
    setToken(null);
    setState({ status: 'signedOut' });
  }, []);

  const value = useMemo(
    () => ({ ...state, login, register, logout }),
    [state, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
