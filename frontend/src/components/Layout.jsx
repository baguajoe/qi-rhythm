import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext.jsx';
import { useSettings } from '../app/settings.jsx';
import Button from './Button.jsx';
import styles from './Layout.module.css';

const LINKS = [
  ['/', 'Class'],
  ['/teams', 'Teams'],
  ['/library', 'Rhythms'],
  ['/calibration', 'Room setup'],
];

export default function Layout() {
  const { instructor, organization, logout } = useAuth();
  const { settings, update } = useSettings();
  return (
    <>
      <a href="#main" className={styles.skip}>
        Skip to main content
      </a>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.logo} aria-hidden="true" />
          <span>
            <strong>Qi Rhythm</strong>
            <span className={styles.org}>{organization?.name}</span>
          </span>
        </div>
        <nav aria-label="Main">
          <ul className={styles.nav}>
            {LINKS.map(([to, label]) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) => (isActive ? styles.active : undefined)}
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className={styles.tools}>
          <Button
            aria-pressed={settings.highContrast}
            onClick={() => update({ highContrast: !settings.highContrast })}
          >
            High contrast {settings.highContrast ? 'on' : 'off'}
          </Button>
          <Button variant="link" onClick={logout}>
            Sign out {instructor?.display_name ? `(${instructor.display_name})` : ''}
          </Button>
        </div>
      </header>
      <main id="main" className="page" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}
