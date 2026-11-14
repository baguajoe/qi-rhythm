import { useState } from 'react';
import Notice from '../../components/Notice.jsx';
import RhythmPicker from './RhythmPicker.jsx';
import RhythmPreview from './RhythmPreview.jsx';
import { useLibrary } from './useLibrary.js';
import styles from './LibraryPage.module.css';

export default function LibraryPage() {
  const { genres, rhythms, loading, error } = useLibrary();
  const [selected, setSelected] = useState(null);
  return (
    <>
      <h1>Rhythm library</h1>
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? (
        <p role="status">Loading rhythms…</p>
      ) : (
        <div className={styles.layout}>
          <RhythmPicker
            genres={genres}
            rhythms={rhythms}
            selectedId={selected?.id}
            onSelect={setSelected}
          />
          {selected ? (
            <RhythmPreview
              rhythm={selected}
              genre={genres.find((g) => g.slug === selected.genre_slug)}
            />
          ) : (
            <p>Pick a rhythm to hear it and see its pattern.</p>
          )}
        </div>
      )}
    </>
  );
}
