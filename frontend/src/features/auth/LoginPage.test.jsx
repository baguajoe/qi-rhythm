import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import LoginPage from './LoginPage.jsx';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';

function setup() {
  return renderApp(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Dashboard home</p>} />
    </Routes>,
    { route: '/login', auth: false },
  );
}

test('signs in and goes to the dashboard', async () => {
  const calls = mockFetch({ 'POST /api/auth/login': { access_token: 'tok', ...ME } });
  setup();
  await userEvent.type(screen.getByLabelText('Email'), 'c@example.com');
  await userEvent.type(screen.getByLabelText('Password'), 'drumcircle1');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByText('Dashboard home')).toBeInTheDocument();
  expect(calls[0].body).toEqual({ email: 'c@example.com', password: 'drumcircle1' });
  expect(localStorage.getItem('qi.token')).toBe('tok');
});

test('shows a plain-language error', async () => {
  mockFetch({
    'POST /api/auth/login': {
      __status: 401,
      error: "That email and password don't match. Please try again.",
    },
  });
  setup();
  await userEvent.type(screen.getByLabelText('Email'), 'c@example.com');
  await userEvent.type(screen.getByLabelText('Password'), 'nope');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent("don't match"));
});

test('can switch to create-account form', async () => {
  mockFetch({});
  setup();
  await userEvent.click(screen.getByRole('button', { name: /create an account/i }));
  expect(screen.getByLabelText('Organization name')).toBeInTheDocument();
  expect(screen.getByText('At least 10 characters.')).toBeInTheDocument();
});
