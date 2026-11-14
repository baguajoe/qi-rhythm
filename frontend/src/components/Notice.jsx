import styles from './Notice.module.css';

/** Status message. Errors are announced assertively; others politely. Never alarming red. */
export default function Notice({ tone = 'info', children }) {
  return (
    <div
      className={`${styles.notice} ${styles[tone]}`}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  );
}
