import { useCallback, useEffect, useState } from 'react';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import styles from './ClassPage.module.css';

/** Load a saved rhythm sequence, step through it, or save this class's rhythms as one. */
export default function ActivityBar({ sessionId, rhythms, roundsPlayed, onSelectRhythm }) {
  const [activities, setActivities] = useState([]);
  const [chosen, setChosen] = useState('');
  const [active, setActive] = useState(null); // { activity, position }
  const [name, setName] = useState('');
  const [msg, setMsg] = useState(null);

  const load = useCallback(() => {
    api('/api/activities')
      .then((d) => setActivities(d.activities))
      .catch(() => {});
  }, []);
  useEffect(load, [load]);

  const goTo = (activity, position) => {
    const id = activity.rhythm_ids[position];
    const r = rhythms.find((x) => x.id === id);
    if (r) onSelectRhythm(r);
    setActive({ activity, position });
  };

  function useActivity() {
    const a = activities.find((x) => String(x.id) === chosen);
    if (a) goTo(a, 0);
  }

  async function save(e) {
    e.preventDefault();
    try {
      await api('/api/activities', { method: 'POST', body: { name, from_session_id: sessionId } });
      setMsg({ tone: 'success', text: `Saved “${name}”.` });
      setName('');
      load();
    } catch (err) {
      setMsg({ tone: 'error', text: err.message });
    }
  }

  return (
    <div className={styles.activities}>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      {active ? (
        <div className={styles.activityNow}>
          <p>
            <strong>{active.activity.name}</strong>: rhythm {active.position + 1} of{' '}
            {active.activity.rhythm_ids.length}
          </p>
          <div className={styles.controls}>
            <Button
              onClick={() => goTo(active.activity, active.position + 1)}
              disabled={active.position + 1 >= active.activity.rhythm_ids.length}
            >
              Next rhythm →
            </Button>
            <Button variant="link" onClick={() => setActive(null)}>
              Stop using activity
            </Button>
          </div>
        </div>
      ) : (
        activities.length > 0 && (
          <div className={styles.row}>
            <Field
              label="Saved activity"
              as="select"
              value={chosen}
              onChange={(e) => setChosen(e.target.value)}
            >
              <option value="">Choose…</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.rhythm_ids.length} rhythms)
                </option>
              ))}
            </Field>
            <Button onClick={useActivity} disabled={!chosen}>
              Use activity
            </Button>
          </div>
        )
      )}
      {roundsPlayed > 0 && (
        <form className={styles.row} onSubmit={save}>
          <Field
            label="Save today's rhythms as an activity"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
            placeholder="e.g. Tuesday Latin set"
          />
          <Button type="submit" disabled={!name.trim()}>
            Save
          </Button>
        </form>
      )}
    </div>
  );
}
