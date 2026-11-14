import { useCallback, useEffect, useState } from 'react';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import TeamBadge from './TeamBadge.jsx';
import { MASCOT_ICONS, TEAM_COLORS } from './teamStyle.js';
import styles from './TeamsPage.module.css';

function ColorPicker({ value, onChange, legend }) {
  return (
    <fieldset className={styles.colors}>
      <legend>{legend}</legend>
      {TEAM_COLORS.map((c) => (
        <label key={c.hex} className={styles.swatch} style={{ background: c.hex }}>
          <input
            type="radio"
            name={legend}
            value={c.hex}
            checked={value === c.hex}
            onChange={() => onChange(c.hex)}
          />
          <span className={styles.swatchName}>{c.name}</span>
        </label>
      ))}
    </fieldset>
  );
}

function IconSelect({ value, onChange }) {
  return (
    <Field
      label="Team icon (optional)"
      as="select"
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">No icon</option>
      {Object.entries(MASCOT_ICONS).map(([key, { emoji, label }]) => (
        <option key={key} value={key}>
          {emoji} {label}
        </option>
      ))}
    </Field>
  );
}

function TeamEditor({ team, onSaved }) {
  const [draft, setDraft] = useState({
    name: team.name,
    color: team.color,
    mascot_icon: team.mascot_icon,
  });
  const [alias, setAlias] = useState('');
  const [msg, setMsg] = useState(null);

  async function save() {
    try {
      const { team: t } = await api(`/api/teams/${team.id}`, { method: 'PATCH', body: draft });
      onSaved(t);
      setMsg({ tone: 'success', text: 'Saved.' });
    } catch (e) {
      setMsg({ tone: 'error', text: e.message });
    }
  }
  async function addAlias(e) {
    e.preventDefault();
    if (!alias.trim()) return;
    try {
      const { team: t } = await api(`/api/teams/${team.id}/participants`, {
        method: 'POST',
        body: { alias },
      });
      onSaved(t);
      setAlias('');
      setMsg(null);
    } catch (err) {
      setMsg({ tone: 'error', text: err.message });
    }
  }
  async function removeAlias(p) {
    const { team: t } = await api(`/api/teams/${team.id}/participants/${p.id}`, {
      method: 'DELETE',
    });
    onSaved(t);
  }
  async function archive() {
    const { team: t } = await api(`/api/teams/${team.id}`, {
      method: 'PATCH',
      body: { is_active: false },
    });
    onSaved(t);
  }

  return (
    <section className={styles.team} aria-labelledby={`team-${team.id}`}>
      <h3 id={`team-${team.id}`}>
        <TeamBadge team={team} size="large" />
      </h3>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Field
        label="Team name"
        value={draft.name}
        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        maxLength={80}
      />
      <ColorPicker
        legend={`Colour for ${team.name}`}
        value={draft.color}
        onChange={(color) => setDraft({ ...draft, color })}
      />
      <IconSelect
        value={draft.mascot_icon}
        onChange={(mascot_icon) => setDraft({ ...draft, mascot_icon })}
      />
      <div className={styles.row}>
        <Button variant="primary" onClick={save}>
          Save changes
        </Button>
        <Button variant="danger" onClick={archive}>
          Put team away
        </Button>
      </div>
      <h4>Members (nicknames only, optional)</h4>
      {team.participants.length > 0 ? (
        <ul className={styles.members}>
          {team.participants.map((p) => (
            <li key={p.id}>
              {p.alias}
              <Button
                variant="link"
                onClick={() => removeAlias(p)}
                aria-label={`Remove ${p.alias}`}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>No nicknames added. That&apos;s fine!</p>
      )}
      <form className={styles.row} onSubmit={addAlias}>
        <Field
          label="Add a nickname"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          maxLength={40}
          hint="First name or nickname only."
        />
        <Button type="submit">Add</Button>
      </form>
    </section>
  );
}

export default function TeamsPage() {
  const [teams, setTeams] = useState([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ name: '', color: TEAM_COLORS[0].hex, mascot_icon: null });

  const load = useCallback(() => {
    api('/api/teams')
      .then((d) => setTeams(d.teams))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function create(e) {
    e.preventDefault();
    setError('');
    try {
      await api('/api/teams', { method: 'POST', body: form });
      const used = new Set([...teams.map((t) => t.color), form.color]);
      setForm({
        name: '',
        color: TEAM_COLORS.find((c) => !used.has(c.hex))?.hex || TEAM_COLORS[0].hex,
        mascot_icon: null,
      });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  const onSaved = (t) =>
    setTeams((ts) =>
      t.is_active ? ts.map((x) => (x.id === t.id ? t : x)) : ts.filter((x) => x.id !== t.id),
    );

  return (
    <>
      <h1>Teams</h1>
      {error && <Notice tone="error">{error}</Notice>}
      <form className={styles.create} onSubmit={create} aria-labelledby="new-team">
        <h2 id="new-team">Make a new team</h2>
        <Field
          label="Team name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          maxLength={80}
          required
        />
        <ColorPicker
          legend="Team colour"
          value={form.color}
          onChange={(color) => setForm({ ...form, color })}
        />
        <IconSelect
          value={form.mascot_icon}
          onChange={(mascot_icon) => setForm({ ...form, mascot_icon })}
        />
        <Button type="submit" variant="primary" size="large">
          Add team
        </Button>
      </form>
      <h2>Your teams</h2>
      {teams.length === 0 && <p>No teams yet. Make two teams to get started.</p>}
      <div className={styles.grid}>
        {teams.map((t) => (
          <TeamEditor key={t.id} team={t} onSaved={onSaved} />
        ))}
      </div>
    </>
  );
}
