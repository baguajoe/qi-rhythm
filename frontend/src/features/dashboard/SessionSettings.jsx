import Slider from '../../components/Slider.jsx';
import styles from './ClassPage.module.css';

const PRESETS = [
  ['gentle', 'Gentle', 'Most forgiving timing. Best for most groups.'],
  ['standard', 'Standard', 'A little more precise.'],
  ['challenge', 'Challenge', 'For experienced players.'],
];

function Toggle({ label, checked, onChange, hint }) {
  return (
    <label className={styles.toggle}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <span className={styles.hint}>{hint}</span>}
      </span>
    </label>
  );
}

export default function SessionSettings({ settings, onChange, baseBpm }) {
  const tempoPct = Math.round(settings.tempo_multiplier * 100);
  return (
    <section className={styles.card} aria-labelledby="settings-title">
      <h2 id="settings-title">Class settings</h2>
      <div className={styles.sliders}>
        <Slider
          label="Speed"
          value={tempoPct}
          min={50}
          max={120}
          step={5}
          onChange={(v) => onChange({ tempo_multiplier: v / 100 })}
          format={(v) => (baseBpm ? `${v}% (${Math.round((baseBpm * v) / 100)} bpm)` : `${v}%`)}
        />
        <Slider
          label="Volume"
          value={Math.round(settings.volume * 100)}
          min={0}
          max={100}
          step={5}
          onChange={(v) => onChange({ volume: v / 100 })}
          format={(v) => `${v}%`}
        />
      </div>
      <fieldset className={styles.presets}>
        <legend>How strict is the timing?</legend>
        {PRESETS.map(([key, label, hint]) => (
          <label
            key={key}
            className={`${styles.preset} ${settings.tolerance_preset === key ? styles.presetOn : ''}`}
          >
            <input
              type="radio"
              name="tolerance"
              value={key}
              checked={settings.tolerance_preset === key}
              onChange={() => onChange({ tolerance_preset: key })}
            />
            <span>
              <strong>{label}</strong>
              <span className={styles.hint}>{hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className={styles.toggles}>
        <Toggle
          label="Spoken instructions"
          hint="The laptop reads instructions aloud."
          checked={settings.spoken_instructions}
          onChange={(v) => onChange({ spoken_instructions: v })}
        />
        {settings.spoken_instructions && (
          <Slider
            label="Speaking speed"
            value={settings.speech_rate}
            min={0.6}
            max={1.3}
            step={0.1}
            onChange={(v) => onChange({ speech_rate: v })}
            format={(v) => `${Number(v).toFixed(1)}×`}
          />
        )}
        <Toggle
          label="High contrast on the TV"
          checked={settings.high_contrast}
          onChange={(v) => onChange({ high_contrast: v })}
        />
        <Toggle
          label="Cooperative mode"
          hint="Hide the team ranking and show one group total."
          checked={settings.cooperative_mode}
          onChange={(v) => onChange({ cooperative_mode: v })}
        />
        <Toggle
          label="Move to the next team automatically"
          hint="After you confirm a score."
          checked={settings.auto_advance}
          onChange={(v) => onChange({ auto_advance: v })}
        />
      </div>
    </section>
  );
}
