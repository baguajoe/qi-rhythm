import { useMemo, useState } from 'react';
import { pickSurprise } from '../../audio/schedule.js';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import { DIFFICULTY_LABEL } from './useLibrary.js';
import styles from './RhythmPicker.module.css';

/** Choose a rhythm by genre and difficulty, or "Surprise me". */
export default function RhythmPicker({ genres, rhythms, selectedId, onSelect }) {
  const [genre, setGenre] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const filtered = useMemo(
    () =>
      rhythms.filter(
        (r) => (!genre || r.genre_slug === genre) && (!difficulty || r.difficulty === difficulty),
      ),
    [rhythms, genre, difficulty],
  );
  const genreName = (slug) => genres.find((g) => g.slug === slug)?.name || '';

  return (
    <div className={styles.picker}>
      <div className={styles.filters}>
        <Field
          label="Music style"
          as="select"
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
        >
          <option value="">All styles</option>
          {genres.map((g) => (
            <option key={g.slug} value={g.slug}>
              {g.name}
            </option>
          ))}
        </Field>
        <Field
          label="Difficulty"
          as="select"
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
        >
          <option value="">Any difficulty</option>
          {Object.entries(DIFFICULTY_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Field>
        <Button onClick={() => onSelect(pickSurprise(filtered))} disabled={!filtered.length}>
          🎲 Surprise me
        </Button>
      </div>
      <p className={styles.count} role="status">
        {filtered.length} {filtered.length === 1 ? 'rhythm' : 'rhythms'}
      </p>
      <ul className={styles.list}>
        {filtered.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              className={`${styles.item} ${r.id === selectedId ? styles.selected : ''}`}
              aria-pressed={r.id === selectedId}
              onClick={() => onSelect(r)}
            >
              <span className={styles.title}>{r.title}</span>
              <span className={styles.meta}>
                {genreName(r.genre_slug)} · {DIFFICULTY_LABEL[r.difficulty]} · {Math.round(r.bpm)}{' '}
                beats per minute
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
