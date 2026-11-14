import { useState } from 'react';
import { effectiveBpm } from '../../audio/schedule.js';
import { usePatternPlayer } from '../../audio/usePatternPlayer.js';
import BeatVisualizer from '../../components/BeatVisualizer.jsx';
import Button from '../../components/Button.jsx';
import Slider from '../../components/Slider.jsx';
import { DIFFICULTY_LABEL } from './useLibrary.js';
import styles from './RhythmPreview.module.css';

export default function RhythmPreview({ rhythm, genre }) {
  const player = usePatternPlayer();
  const [tempo, setTempo] = useState(100);
  const [volume, setVolume] = useState(80);
  const bpm = effectiveBpm(rhythm.bpm, tempo);

  return (
    <section className={styles.preview} aria-labelledby="preview-title">
      <h2 id="preview-title">{rhythm.title}</h2>
      <p className={styles.meta}>
        {genre?.name} · {DIFFICULTY_LABEL[rhythm.difficulty]} · {rhythm.time_signature} ·{' '}
        {rhythm.pattern.events.length} hits
      </p>
      <BeatVisualizer
        pattern={rhythm.pattern}
        lengthBeats={rhythm.length_beats}
        playedThrough={player.playing ? player.playedThrough : -1}
      />
      <div className={styles.controls}>
        {player.playing ? (
          <Button variant="primary" size="large" onClick={player.stop}>
            ■ Stop
          </Button>
        ) : (
          <Button
            variant="primary"
            size="large"
            onClick={() =>
              player.play(rhythm.pattern, bpm, {
                lengthBeats: rhythm.length_beats,
                volume: volume / 100,
              })
            }
          >
            ▶ Play the pattern
          </Button>
        )}
        <Slider
          label="Speed"
          value={tempo}
          min={50}
          max={120}
          step={5}
          onChange={setTempo}
          format={(v) => `${v}% (${Math.round(effectiveBpm(rhythm.bpm, v))} bpm)`}
        />
        <Slider
          label="Volume"
          value={volume}
          min={0}
          max={100}
          step={5}
          onChange={setVolume}
          format={(v) => `${v}%`}
        />
      </div>
      {genre?.cultural_notes && (
        <div className={styles.notes}>
          <h3>About {genre.name}</h3>
          <p>{genre.cultural_notes}</p>
        </div>
      )}
    </section>
  );
}
