import Button from '../../components/Button.jsx';
import Notice from '../../components/Notice.jsx';
import { OriginalBadge } from '../music/MusicPage.jsx';
import styles from './ClassPage.module.css';

/**
 * The backing tracks that play for one rhythm, as { full, bed } (either may be null). The server
 * marks them `in_use`: the organization's own usable loop, else the Qi Rhythm Library's.
 */
export function musicFromTracks(tracks) {
  const usable = (v) =>
    tracks.find((t) => t.version === v && t.usable && (t.in_use ?? true)) || null;
  const full = usable('full');
  const bed = usable('bed');
  return full || bed ? { full, bed } : null;
}

function describe(music) {
  if (music.full && music.bed) return 'Full version while listening, groove only for the turn.';
  if (music.full) return 'Full version while listening. The turn uses the count-in only.';
  return 'Groove plays under the pattern and under the turn.';
}

/** Shows what music this rhythm will use and offers "Measure music level" for the groove. */
export default function MusicPanel({ rhythm, music, musicOn, busy, measuring, onMeasure }) {
  if (!rhythm) return null;
  const bed = music?.bed;
  return (
    <section className={styles.card} aria-labelledby="music-title">
      <h2 id="music-title">Backing music</h2>
      {!music && <p>This rhythm uses the built-in drum sounds.</p>}
      {music && !musicOn && <p>Backing music is off. Turn it on in Class settings.</p>}
      {music && musicOn && (
        <>
          <p>{describe(music)}</p>
          {[music.full, music.bed].some((t) => t?.badge) && (
            <p>
              <OriginalBadge track={[music.full, music.bed].find((t) => t?.badge)} /> From the Qi
              Rhythm Library.
            </p>
          )}
          {bed && (
            <>
              {bed.music_level ? (
                <p className={styles.hint}>
                  Music level measured{' '}
                  {new Date(bed.music_level.created_at).toLocaleString([], {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}
                  .
                </p>
              ) : (
                <Notice tone="review">
                  Measure the music level once before the first turn, so the app can tell the music
                  apart from your team&apos;s playing.
                </Notice>
              )}
              <p className={styles.hint}>
                Ask everyone to stay quiet for about 10 seconds while the music plays.
              </p>
              <div className={styles.controls}>
                <Button onClick={onMeasure} disabled={busy}>
                  {measuring ? 'Measuring…' : '🎚 Measure music level'}
                </Button>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
