import { useId } from 'react';
import styles from './Field.module.css';

/** Labelled form field with optional hint and error, wired up for screen readers. */
export default function Field({ label, hint, error, as = 'input', children, ...props }) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const Control = as;
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      {hint && (
        <span id={hintId} className={styles.hint}>
          {hint}
        </span>
      )}
      <Control
        id={id}
        className={styles.control}
        aria-describedby={[hintId, errId].filter(Boolean).join(' ') || undefined}
        aria-invalid={error ? true : undefined}
        {...props}
      >
        {children}
      </Control>
      {error && (
        <span id={errId} className={styles.error}>
          {error}
        </span>
      )}
    </div>
  );
}
