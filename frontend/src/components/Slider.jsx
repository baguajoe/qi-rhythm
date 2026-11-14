import { useId } from 'react';
import styles from './Slider.module.css';

/** Large, labelled range input that announces a human-readable value. */
export default function Slider({ label, value, min, max, step = 1, onChange, format = (v) => v }) {
  const id = useId();
  return (
    <div className={styles.slider}>
      <label htmlFor={id}>
        {label}: <strong>{format(value)}</strong>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={String(format(value))}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
