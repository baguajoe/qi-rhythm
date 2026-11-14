import { useState } from 'react';
import Button from '../../components/Button.jsx';
import Notice from '../../components/Notice.jsx';
import { CATEGORY_LABELS, confidenceLevel, messageFor, starsFor } from '../../lib/encouragement.js';
import AdjustScoreForm from './AdjustScoreForm.jsx';
import ScoreTimeline from './ScoreTimeline.jsx';
import styles from './ScorePanel.module.css';

export function Stars({ total }) {
  const n = starsFor(total);
  return (
    <span className={styles.stars} role="img" aria-label={`${n} out of 5 stars`}>
      {'★'.repeat(n)}
      <span className={styles.dim}>{'☆'.repeat(5 - n)}</span>
    </span>
  );
}

export default function ScorePanel({ round, score, onConfirm, onOverride }) {
  const [adjusting, setAdjusting] = useState(false);
  const eff = score.effective;
  const conf = confidenceLevel(score.confidence);

  return (
    <section className={styles.panel} aria-labelledby="score-title">
      <h2 id="score-title">
        {round.team.name}: {Math.round(eff.total)} points
      </h2>
      <p className={styles.cheer}>
        <Stars total={eff.total} /> {messageFor(eff.total, round.id)}
      </p>
      {score.needs_review && !score.confirmed && (
        <Notice tone="review">
          <strong>Audio was unclear — confirm or adjust this score.</strong>
          <ul>
            {score.review_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Notice>
      )}
      <dl className={styles.breakdown}>
        {Object.entries(CATEGORY_LABELS).map(([k, label]) => (
          <div key={k} className={styles.cat}>
            <dt>{label}</dt>
            <dd>
              <span className={styles.bar} aria-hidden="true">
                <span style={{ width: `${eff[k]}%` }} />
              </span>
              <strong>{Math.round(eff[k])}</strong>
              {score.is_override && eff[k] !== score.machine[k] && (
                <span className={styles.was}> (was {Math.round(score.machine[k])})</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {score.is_override && (
        <p>
          Adjusted by instructor (computer total was {Math.round(score.machine.total)})
          {score.override_reason ? `: ${score.override_reason}` : '.'}
        </p>
      )}
      <p className={`${styles.conf} ${styles[conf.key]}`}>
        <span className={styles.confBars} aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        {conf.label} ({Math.round(score.confidence * 100)}% sure)
      </p>
      <ScoreTimeline alignment={score.alignment} />
      {adjusting ? (
        <AdjustScoreForm
          score={score}
          onCancel={() => setAdjusting(false)}
          onSave={async (body) => {
            await onOverride(body);
            setAdjusting(false);
          }}
        />
      ) : (
        <div className={styles.row}>
          {!score.confirmed ? (
            <Button variant="primary" size="large" onClick={onConfirm}>
              ✓ Confirm score
            </Button>
          ) : (
            <span className={styles.confirmed}>✓ Score confirmed</span>
          )}
          <Button size="large" onClick={() => setAdjusting(true)}>
            Adjust score
          </Button>
        </div>
      )}
    </section>
  );
}
