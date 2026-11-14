import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsProvider } from '../app/settings.jsx';
import { AuthProvider } from '../features/auth/AuthContext.jsx';

/** Mock fetch with a route table: { 'GET /api/teams': body | (req) => body }. */
export function mockFetch(routes) {
  const calls = [];
  global.fetch = vi.fn(async (url, init = {}) => {
    const method = init.method || 'GET';
    const path = url.replace(/^https?:\/\/[^/]+/, '');
    const key = `${method} ${path.split('?')[0]}`;
    calls.push({ key, path, body: init.body ? JSON.parse(init.body) : undefined });
    const handler = routes[key];
    if (!handler) return { ok: false, status: 404, json: async () => ({ error: 'Not found.' }) };
    const out = typeof handler === 'function' ? handler(calls.at(-1)) : handler;
    const status = out?.__status || 200;
    return { ok: status < 400, status, json: async () => out };
  });
  return calls;
}

export function renderApp(ui, { route = '/', auth = true } = {}) {
  if (auth) localStorage.setItem('qi.token', 'test-token');
  else localStorage.removeItem('qi.token');
  return render(
    <MemoryRouter
      initialEntries={[route]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <SettingsProvider>
        <AuthProvider>{ui}</AuthProvider>
      </SettingsProvider>
    </MemoryRouter>,
  );
}

export const ME = {
  instructor: { id: 1, display_name: 'Coach Lee', email: 'c@example.com', role: 'admin' },
  organization: { id: 1, name: 'Maple Grove' },
};
