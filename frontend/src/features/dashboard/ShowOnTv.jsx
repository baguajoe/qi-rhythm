import { useState } from 'react';
import Button from '../../components/Button.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import styles from './ClassPage.module.css';

/** Pair a TV/projector: short code (or one-click window on this laptop). */
export default function ShowOnTv({ sessionId, socketStatus }) {
  const [pairing, setPairing] = useState(null);
  const [error, setError] = useState('');

  async function makeCode() {
    setError('');
    try {
      setPairing(await api(`/api/sessions/${sessionId}/display-code`, { method: 'POST' }));
    } catch (e) {
      setError(e.message);
    }
  }

  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return (
    <section className={styles.card} aria-labelledby="tv-title">
      <h2 id="tv-title">Show on the TV</h2>
      {error && <Notice tone="error">{error}</Notice>}
      {!pairing ? (
        <Button variant="primary" onClick={makeCode}>
          Get a TV code
        </Button>
      ) : (
        <>
          <p>
            Open the TV screen in a new window and drag it to the TV, or on another device go to{' '}
            <strong>
              {origin}/display/{sessionId}
            </strong>{' '}
            and enter this code:
          </p>
          <p className={styles.tvCode} aria-label={`TV code ${pairing.code.split('').join(' ')}`}>
            {pairing.code}
          </p>
          <div className={styles.controls}>
            <Button
              variant="primary"
              onClick={() => window.open(pairing.path, 'qi-display', 'noopener')}
            >
              Open TV screen in a new window
            </Button>
            <Button onClick={makeCode}>New code</Button>
          </div>
          <p className={styles.hint}>
            The code works for 15 minutes. The TV stays connected for the whole class.
          </p>
        </>
      )}
      <p className={styles.hint} role="status">
        Live connection: {socketStatus === 'connected' ? 'connected' : 'reconnecting…'}
      </p>
      {/* TODO(phase-3): render the pairing link as a QR code (needs a small QR library). */}
    </section>
  );
}
