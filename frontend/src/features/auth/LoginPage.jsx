import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import Notice from '../../components/Notice.jsx';
import { useAuth } from './AuthContext.jsx';
import styles from './LoginPage.module.css';

const ORG_TYPES = [
  ['senior_center', 'Senior center'],
  ['assisted_living', 'Assisted living'],
  ['adult_day', 'Adult day program'],
  ['community_org', 'Community organization'],
  ['other', 'Other'],
];

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    email: '',
    password: '',
    display_name: '',
    organization_name: '',
    organization_type: 'senior_center',
  });
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') await login(form.email, form.password);
      else await register(form);
      navigate(location.state?.from?.pathname || '/', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === 'login';
  return (
    <main className={`page ${styles.wrap}`} id="main">
      <h1>Qi Rhythm</h1>
      <p className={styles.tagline}>Rhythm, memory, and team games for your group.</p>
      <form className={styles.card} onSubmit={onSubmit} noValidate>
        <h2>{isLogin ? 'Sign in' : 'Create your account'}</h2>
        {error && <Notice tone="error">{error}</Notice>}
        {!isLogin && (
          <>
            <Field
              label="Your name"
              value={form.display_name}
              onChange={set('display_name')}
              autoComplete="name"
              required
            />
            <Field
              label="Organization name"
              value={form.organization_name}
              onChange={set('organization_name')}
              autoComplete="organization"
              required
            />
            <Field
              label="Type of organization"
              as="select"
              value={form.organization_type}
              onChange={set('organization_type')}
            >
              {ORG_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Field>
          </>
        )}
        <Field
          label="Email"
          type="email"
          value={form.email}
          onChange={set('email')}
          autoComplete="email"
          required
        />
        <Field
          label="Password"
          type="password"
          value={form.password}
          onChange={set('password')}
          autoComplete={isLogin ? 'current-password' : 'new-password'}
          hint={isLogin ? undefined : 'At least 10 characters.'}
          required
        />
        <Button type="submit" variant="primary" size="large" disabled={busy}>
          {busy ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
        </Button>
        <Button
          type="button"
          variant="link"
          onClick={() => {
            setMode(isLogin ? 'register' : 'login');
            setError('');
          }}
        >
          {isLogin ? 'New here? Create an account' : 'Already have an account? Sign in'}
        </Button>
      </form>
    </main>
  );
}
