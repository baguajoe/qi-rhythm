import styles from './LevelMeter.module.css';

/** Live microphone level. `level` is linear RMS (0-1); shown on a dB scale. */
export default function LevelMeter({ level = 0, label = 'Microphone level', size = 'normal' }) {
  const db = 20 * Math.log10(Math.max(level, 1e-5));
  const pct = Math.round(Math.min(100, Math.max(0, ((db + 60) / 60) * 100)));
  return (
    <div className={`${styles.meter} ${styles[size]}`}>
      <span className={styles.label}>{label}</span>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className={styles.track}
      >
        <div className={styles.fill} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
