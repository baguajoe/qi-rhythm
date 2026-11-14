import { useState } from 'react';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import { CATEGORY_LABELS } from '../../lib/encouragement.js';
import styles from './ScorePanel.module.css';

/** Instructor override. Leave total blank to recalculate it from the categories. */
export default function AdjustScoreForm({ score, onSave, onCancel }) {
  const start = score.effective;
  const [values, setValues] = useState({
    ...Object.fromEntries(Object.keys(CATEGORY_LABELS).map((k) => [k, start[k]])),
    total: '',
  });
  const [reason, setReason] = useState('');

  function submit(e) {
    e.preventDefault();
    const body = { reason };
    for (const [k, v] of Object.entries(values)) {
      if (v === '' || v === null) continue;
      if (k === 'total' || Number(v) !== start[k]) body[k] = Number(v);
    }
    onSave(body);
  }

  return (
    <form className={styles.adjust} onSubmit={submit} aria-labelledby="adjust-title">
      <h3 id="adjust-title">Adjust score</h3>
      <p>The original computer score is kept. Your changes are saved separately.</p>
      <div className={styles.adjustGrid}>
        {Object.entries(CATEGORY_LABELS).map(([k, label]) => (
          <Field
            key={k}
            label={label}
            type="number"
            min={0}
            max={100}
            step={1}
            value={values[k]}
            onChange={(e) => setValues({ ...values, [k]: e.target.value })}
          />
        ))}
        <Field
          label="Total (optional)"
          hint="Leave empty to work it out from the scores above."
          type="number"
          min={0}
          max={100}
          step={1}
          value={values.total}
          onChange={(e) => setValues({ ...values, total: e.target.value })}
        />
      </div>
      <Field
        label="Reason (optional)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={255}
      />
      <div className={styles.row}>
        <Button type="submit" variant="primary">
          Save score
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
