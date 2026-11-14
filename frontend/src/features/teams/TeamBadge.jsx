import { textOn } from '../../lib/contrast.js';
import { MASCOT_ICONS } from './teamStyle.js';
import styles from './TeamBadge.module.css';

export default function TeamBadge({ team, size = 'normal' }) {
  const icon = team.mascot_icon && MASCOT_ICONS[team.mascot_icon];
  return (
    <span
      className={`${styles.badge} ${styles[size]}`}
      style={{ background: team.color, color: textOn(team.color) }}
    >
      {icon && (
        <span role="img" aria-label={icon.label}>
          {icon.emoji}
        </span>
      )}
      {team.name}
    </span>
  );
}
