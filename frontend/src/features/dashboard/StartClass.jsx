import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import styles from './ClassPage.module.css';

export default function StartClass({ onStart }) {
  const [profiles, setProfiles] = useState(null);
  const [profileId, setProfileId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/calibration')
      .then((d) => {
        setProfiles(d.profiles);
        if (d.profiles[0]) setProfileId(String(d.profiles[0].id));
      })
      .catch(() => setProfiles([]));
  }, []);

  async function start() {
    setBusy(true);
    setError('');
    try {
      await onStart({ calibration_profile_id: profileId ? Number(profileId) : null });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="start-title">
      <h2 id="start-title">Start a class</h2>
      {error && <Notice tone="error">{error}</Notice>}
      <Notice tone="info">
        <strong>About recording:</strong> during each team&apos;s turn, the microphone records the
        room so the app can hear the drums. Recordings are used only for scoring and are deleted
        automatically after a few days. You can delete them any time.
      </Notice>
      {profiles && profiles.length === 0 && (
        <p>
          Tip: run <Link to="/calibration">Room setup</Link> first so scoring works best in your
          room.
        </p>
      )}
      {profiles && profiles.length > 0 && (
        <Field
          label="Room setup to use"
          as="select"
          value={profileId}
          onChange={(e) => setProfileId(e.target.value)}
        >
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.device_label}
            </option>
          ))}
          <option value="">None</option>
        </Field>
      )}
      <Button variant="primary" size="huge" onClick={start} disabled={busy}>
        ▶ Start class session
      </Button>
    </section>
  );
}
