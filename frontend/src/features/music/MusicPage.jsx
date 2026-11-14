import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { useDocumentTitle } from '../../app/useDocumentTitle.js';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { useLibrary } from '../library/useLibrary.js';
import styles from './MusicPage.module.css';

export const VERSIONS = [
  ['full', 'Full', 'The groove with the pattern audible. Plays while the team listens.'],
  ['bed', 'Groove only', 'The groove without the pattern. Plays under the team’s turn.'],
];
export const SOURCES = [
  ['', 'Not set yet'],
  ['original', 'Original (I made it)'],
  ['commissioned', 'Commissioned (made for us)'],
  ['licensed', 'Licensed (from a library or label)'],
];
const VERSION_LABEL = Object.fromEntries(VERSIONS.map(([k, label]) => [k, label]));

/** Pulses per bar in the library's beat units (dotted quarter in compound meters). */
export function beatsPerBar(timeSignature = '4/4') {
  const [num, den] = timeSignature.split('/').map(Number);
  if (den === 8 && num % 3 === 0 && num > 3) return num / 3;
  return num || 4;
}

export function expectedSeconds(bpm, bars, perBar) {
  const b = Number(bpm);
  const n = Number(bars);
  if (!(b > 0) || !(n > 0)) return null;
  return (n * perBar * 60) / b;
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

function DurationLine({ track }) {
  const ok =
    Math.abs(track.duration_s - track.expected_duration_s) <=
    Math.max(0.05, 0.01 * track.expected_duration_s);
  return (
    <p>
      Detected length <strong>{track.duration_s.toFixed(2)} s</strong> · expected{' '}
      <strong>{track.expected_duration_s.toFixed(2)} s</strong> ({plural(track.bars, 'bar')} ×{' '}
      {track.beats_per_bar} beats at {track.bpm} BPM){' '}
      {ok ? <span className={styles.ok}>✓ matches</span> : <span>· doesn’t match</span>}
    </p>
  );
}

function Preview({ track }) {
  const [url, setUrl] = useState(null);
  const [error, setError] = useState('');
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  async function load() {
    setError('');
    try {
      const res = await api(track.audio_path, { raw: true });
      if (!res.ok) throw new Error('The file could not be loaded.');
      setUrl(URL.createObjectURL(await res.blob()));
    } catch (e) {
      setError(e.message);
    }
  }
  if (url)
    return (
      // eslint-disable-next-line jsx-a11y/media-has-caption -- instrumental loop, no speech
      <audio controls src={url} aria-label={`${VERSION_LABEL[track.version]} loop`} />
    );
  return (
    <>
      <Button onClick={load}>▶ Listen to this loop</Button>
      {error && <Notice tone="error">{error}</Notice>}
    </>
  );
}

function LicenseFields({ draft, setDraft, idPrefix }) {
  return (
    <>
      <Field
        label="Where is this track from?"
        as="select"
        value={draft.source || ''}
        onChange={(e) => setDraft((d) => ({ ...d, source: e.target.value }))}
        name={`${idPrefix}-source`}
      >
        {SOURCES.map(([v, label]) => (
          <option key={v} value={v}>
            {label}
          </option>
        ))}
      </Field>
      <Field
        label="License notes"
        hint="Who owns it and what use is allowed (for example: “Recorded by me in Cubase, 2026” or the license number and terms). Required before the track can be used in a class."
        as="textarea"
        rows={3}
        value={draft.license_notes || ''}
        onChange={(e) => setDraft((d) => ({ ...d, license_notes: e.target.value }))}
      />
    </>
  );
}

function TrackCard({ track, onChanged, onDeleted }) {
  const [draft, setDraft] = useState({
    bpm: track.bpm,
    bars: track.bars,
    notes: track.notes,
    source: track.source || '',
    license_notes: track.license_notes,
  });
  const [msg, setMsg] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const titleId = useId();

  async function save() {
    setMsg(null);
    try {
      const { track: t } = await api(`/api/backing-tracks/${track.id}`, {
        method: 'PATCH',
        body: { ...draft, source: draft.source || null },
      });
      onChanged(t);
      setMsg({ tone: 'success', text: 'Saved.' });
    } catch (e) {
      setMsg({ tone: 'error', text: e.message });
    }
  }

  async function remove() {
    try {
      await api(`/api/backing-tracks/${track.id}`, { method: 'DELETE' });
      onDeleted(track.id);
    } catch (e) {
      setMsg({ tone: 'error', text: e.message });
    }
  }

  return (
    <article className={styles.track} aria-labelledby={titleId}>
      <h3 id={titleId}>
        {VERSION_LABEL[track.version]}{' '}
        <span className={track.usable ? styles.ready : styles.notReady}>
          {track.usable ? 'Ready for classes' : 'Not ready yet'}
        </span>
      </h3>
      <p className={styles.meta}>
        {track.original_filename || 'Uploaded WAV'} · {track.sample_rate / 1000} kHz ·{' '}
        {track.channels === 1 ? 'mono' : 'stereo'}
      </p>
      <DurationLine track={track} />
      {track.warnings.map((w) => (
        <Notice key={w} tone="review">
          {w}
        </Notice>
      ))}
      <Preview key={track.rev} track={track} />
      <div className={styles.row}>
        <Field
          label="BPM"
          type="number"
          min={30}
          max={300}
          step="0.01"
          value={draft.bpm}
          onChange={(e) => setDraft((d) => ({ ...d, bpm: e.target.value }))}
        />
        <Field
          label="Bars"
          type="number"
          min={1}
          max={64}
          value={draft.bars}
          onChange={(e) => setDraft((d) => ({ ...d, bars: e.target.value }))}
        />
      </div>
      <Field
        label="Notes"
        as="textarea"
        rows={2}
        value={draft.notes}
        onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
      />
      <LicenseFields draft={draft} setDraft={setDraft} idPrefix={`t${track.id}`} />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className={styles.row}>
        <Button variant="primary" onClick={save}>
          Save changes
        </Button>
        {confirmDelete ? (
          <>
            <Button variant="danger" onClick={remove}>
              Yes, delete this loop
            </Button>
            <Button onClick={() => setConfirmDelete(false)}>Keep it</Button>
          </>
        ) : (
          <Button onClick={() => setConfirmDelete(true)}>Delete…</Button>
        )}
      </div>
    </article>
  );
}

function UploadForm({ rhythm, onUploaded }) {
  const perBar = beatsPerBar(rhythm.time_signature);
  const blank = useCallback(
    () => ({
      file: null,
      version: 'full',
      bpm: rhythm.bpm,
      bars: Math.max(1, Math.round(rhythm.length_beats / perBar)),
      notes: '',
      source: '',
      license_notes: '',
    }),
    [rhythm, perBar],
  );
  const [draft, setDraft] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [fileKey, setFileKey] = useState(0);
  useEffect(() => {
    setDraft(blank());
    setMsg(null);
  }, [blank]);

  const expected = expectedSeconds(draft.bpm, draft.bars, perBar);

  async function submit(e) {
    e.preventDefault();
    setMsg(null);
    if (!draft.file) {
      setMsg({ tone: 'error', text: 'Please choose a WAV file to upload.' });
      return;
    }
    const form = new FormData();
    form.append('audio', draft.file, draft.file.name);
    for (const k of ['version', 'bpm', 'bars', 'notes', 'source', 'license_notes'])
      form.append(k, String(draft[k] ?? ''));
    setBusy(true);
    try {
      const { track } = await api(`/api/rhythms/${rhythm.id}/backing-tracks`, {
        method: 'POST',
        body: form,
      });
      onUploaded(track);
      setDraft(blank());
      setFileKey((k) => k + 1);
      setMsg({
        tone: 'success',
        text: `Uploaded the ${VERSION_LABEL[track.version].toLowerCase()} loop.`,
      });
    } catch (err) {
      setMsg({ tone: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.upload} onSubmit={submit} aria-labelledby="upload-title">
      <h2 id="upload-title">Upload a loop</h2>
      <p className={styles.meta}>
        WAV, 44.1 kHz or 48 kHz. Uploading a version that already exists replaces it.
      </p>
      <Field
        key={fileKey}
        label="WAV file"
        type="file"
        accept=".wav,audio/wav,audio/x-wav,audio/wave"
        onChange={(e) => setDraft((d) => ({ ...d, file: e.target.files?.[0] || null }))}
      />
      <fieldset className={styles.versions}>
        <legend>Version</legend>
        {VERSIONS.map(([key, label, hint]) => (
          <label key={key} className={styles.version}>
            <input
              type="radio"
              name="version"
              value={key}
              checked={draft.version === key}
              onChange={() => setDraft((d) => ({ ...d, version: key }))}
            />
            <span>
              <strong>{label}</strong>
              <span className={styles.meta}>{hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className={styles.row}>
        <Field
          label="BPM"
          type="number"
          min={30}
          max={300}
          step="0.01"
          value={draft.bpm}
          onChange={(e) => setDraft((d) => ({ ...d, bpm: e.target.value }))}
        />
        <Field
          label="Bars"
          type="number"
          min={1}
          max={64}
          value={draft.bars}
          onChange={(e) => setDraft((d) => ({ ...d, bars: e.target.value }))}
        />
      </div>
      {expected && (
        <p className={styles.meta}>
          At {draft.bpm} BPM, {plural(Number(draft.bars), 'bar')} of {perBar} beats should be{' '}
          {expected.toFixed(2)} s long. We&apos;ll check the file against this.
        </p>
      )}
      <Field
        label="Notes (optional)"
        as="textarea"
        rows={2}
        value={draft.notes}
        onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
      />
      <LicenseFields draft={draft} setDraft={setDraft} idPrefix="new" />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Button type="submit" variant="primary" disabled={busy}>
        {busy ? 'Uploading…' : 'Upload loop'}
      </Button>
    </form>
  );
}

export default function MusicPage() {
  useDocumentTitle('Backing music');
  const { instructor } = useAuth();
  const { genres, rhythms, error: libError } = useLibrary();
  const [rhythmId, setRhythmId] = useState('');
  const [tracks, setTracks] = useState([]);
  const [error, setError] = useState('');
  const [uploads, setUploads] = useState(0); // remount edit cards after a new file replaces one
  const rhythm = rhythms.find((r) => String(r.id) === String(rhythmId)) || null;
  const isAdmin = instructor?.role === 'admin';

  useEffect(() => {
    if (!rhythmId) return undefined;
    let live = true;
    setError('');
    api(`/api/backing-tracks?rhythm_id=${rhythmId}`)
      .then((d) => live && setTracks(d.tracks))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [rhythmId]);

  const grouped = useMemo(
    () =>
      genres
        .map((g) => ({ genre: g, items: rhythms.filter((r) => r.genre_slug === g.slug) }))
        .filter((g) => g.items.length),
    [genres, rhythms],
  );

  const replace = (t) =>
    setTracks((ts) =>
      [...ts.filter((x) => x.id !== t.id && x.version !== t.version), t].sort((a, b) =>
        a.version.localeCompare(b.version),
      ),
    );

  return (
    <>
      <h1>Backing music</h1>
      <p>
        Add your own loops to a rhythm. The <strong>full</strong> version plays while the team
        listens; the <strong>groove only</strong> version plays under the team&apos;s turn. Rhythms
        without loops use the built-in drum sounds.
      </p>
      {!isAdmin && <Notice tone="info">Only an admin can add or change backing music.</Notice>}
      {(libError || error) && <Notice tone="error">{libError || error}</Notice>}
      <div className={styles.picker}>
        <Field
          label="Rhythm"
          as="select"
          value={rhythmId}
          onChange={(e) => {
            setTracks([]);
            setRhythmId(e.target.value);
          }}
        >
          <option value="">Choose a rhythm…</option>
          {grouped.map(({ genre, items }) => (
            <optgroup key={genre.slug} label={genre.name}>
              {items.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} ({r.bpm} BPM, {r.length_beats} beats)
                </option>
              ))}
            </optgroup>
          ))}
        </Field>
      </div>

      {rhythm && (
        <div className={styles.grid}>
          <section className={styles.tracks} aria-labelledby="tracks-title">
            <h2 id="tracks-title">Loops for {rhythm.title}</h2>
            {tracks.length === 0 && <p>No loops yet. This rhythm uses the built-in drum sounds.</p>}
            {tracks.map((t) =>
              isAdmin ? (
                <TrackCard
                  key={`${t.id}-${uploads}`}
                  track={t}
                  onChanged={replace}
                  onDeleted={(id) => setTracks((ts) => ts.filter((x) => x.id !== id))}
                />
              ) : (
                <article key={t.id} className={styles.track}>
                  <h3>{VERSION_LABEL[t.version]}</h3>
                  <DurationLine track={t} />
                </article>
              ),
            )}
          </section>
          {isAdmin && (
            <UploadForm
              rhythm={rhythm}
              onUploaded={(t) => {
                replace(t);
                setUploads((n) => n + 1);
              }}
            />
          )}
        </div>
      )}
    </>
  );
}
