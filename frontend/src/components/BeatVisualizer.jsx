import { sortedEvents } from '../audio/schedule.js';
import styles from './BeatVisualizer.module.css';

const VOICE_LABEL = { low: 'low drum', high: 'high drum', shaker: 'shaker', clap: 'clap' };

/**
 * Circles for each hit in the pattern, positioned by beat. Hits that have played stay lit (no
 * on/off flashing); the current hit gets a thick ring. Every audio cue gets a visual cue.
 */
export default function BeatVisualizer({
  pattern,
  lengthBeats,
  playedThrough = -1,
  size = 'normal',
  label,
}) {
  const events = sortedEvents(pattern);
  const length = lengthBeats || pattern?.length_beats || 8;
  const beats = Array.from({ length: Math.ceil(length) }, (_, i) => i);
  return (
    <div
      className={`${styles.wrap} ${styles[size]}`}
      role="img"
      aria-label={label || `Rhythm pattern with ${events.length} hits over ${length} beats`}
    >
      <div className={styles.track}>
        {beats.map((b) => (
          <span
            key={`b${b}`}
            className={styles.beatLine}
            style={{ left: `${(b / length) * 100}%` }}
            aria-hidden="true"
          />
        ))}
        {events.map((e) => {
          const state =
            e.index < playedThrough ? 'played' : e.index === playedThrough ? 'current' : 'waiting';
          return (
            <span
              key={e.index}
              className={`${styles.hit} ${styles[e.voice] || ''} ${styles[state]} ${e.accent ? styles.accent : ''}`}
              style={{ left: `${(e.beat / length) * 100}%` }}
              title={VOICE_LABEL[e.voice]}
              aria-hidden="true"
            />
          );
        })}
      </div>
    </div>
  );
}
