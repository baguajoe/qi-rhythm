import { useId } from 'react';
import styles from './ScoreTimeline.module.css';

/**
 * Reference hits (top row) vs heard hits (bottom row). Matched = filled circles joined by a line,
 * missed = dashed hollow circle, extra = triangle. Shape + colour + legend, never colour alone.
 */
export default function ScoreTimeline({ alignment }) {
  const titleId = useId();
  if (!alignment?.expected?.length) return null;
  const {
    expected,
    detected_s: detected = [],
    matched = [],
    missed = [],
    extras = [],
    global_offset_ms: offsetMs = 0,
  } = alignment;
  const offset = offsetMs / 1000;
  const [lo, hi] = alignment.window_s || [expected[0].time_s - 0.5, expected.at(-1).time_s + 0.5];
  const W = 1000;
  const x = (t) => 30 + ((t - lo) / Math.max(0.001, hi - lo)) * (W - 60);
  const yRef = 40;
  const yHeard = 120;
  const missedSet = new Set(missed);
  const summary = `${matched.length} of ${expected.length} hits matched, ${missed.length} missed, ${extras.length} extra.`;

  return (
    <figure className={styles.figure}>
      <svg viewBox={`0 0 ${W} 170`} className={styles.svg} role="img" aria-labelledby={titleId}>
        <title id={titleId}>Timeline. {summary}</title>
        <text x="4" y={yRef - 22} className={styles.rowLabel}>
          Pattern
        </text>
        <text x="4" y={yHeard + 36} className={styles.rowLabel}>
          Heard
        </text>
        <line x1="20" x2={W - 20} y1={yRef} y2={yRef} className={styles.axis} />
        <line x1="20" x2={W - 20} y1={yHeard} y2={yHeard} className={styles.axis} />
        {matched.map((m) => (
          <line
            key={`l${m.expected_index}`}
            x1={x(m.expected_s)}
            y1={yRef}
            x2={x(m.detected_s - offset)}
            y2={yHeard}
            className={styles.link}
          />
        ))}
        {expected.map((e) =>
          missedSet.has(e.index) ? (
            <circle
              key={`e${e.index}`}
              cx={x(e.time_s)}
              cy={yRef}
              r="13"
              className={styles.missed}
            />
          ) : (
            <circle
              key={`e${e.index}`}
              cx={x(e.time_s)}
              cy={yRef}
              r="13"
              className={styles.matched}
            />
          ),
        )}
        {matched.map((m) => (
          <circle
            key={`d${m.detected_index}`}
            cx={x(m.detected_s - offset)}
            cy={yHeard}
            r="13"
            className={styles.matched}
          />
        ))}
        {extras.map((j) => {
          const cx = x(detected[j] - offset);
          return (
            <polygon
              key={`x${j}`}
              points={`${cx},${yHeard - 14} ${cx + 14},${yHeard + 12} ${cx - 14},${yHeard + 12}`}
              className={styles.extra}
            />
          );
        })}
      </svg>
      <figcaption className={styles.legend}>
        <span>
          <svg width="24" height="24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" className={styles.matched} />
          </svg>
          Matched
        </span>
        <span>
          <svg width="24" height="24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" className={styles.missed} />
          </svg>
          Missed
        </span>
        <span>
          <svg width="24" height="24" aria-hidden="true">
            <polygon points="12,2 22,21 2,21" className={styles.extra} />
          </svg>
          Extra
        </span>
        <span className={styles.summary}>{summary}</span>
      </figcaption>
    </figure>
  );
}
