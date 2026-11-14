import styles from './Button.module.css';

/** Accessible button: >= 56px tall, visible focus, plain-language label. */
export default function Button({
  variant = 'secondary',
  size = 'normal',
  className = '',
  ...props
}) {
  return (
    <button
      type="button"
      className={`${styles.btn} ${styles[variant]} ${styles[size]} ${className}`}
      {...props}
    />
  );
}
