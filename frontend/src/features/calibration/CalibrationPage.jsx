import { useDocumentTitle } from '../../app/useDocumentTitle.js';
import { useEffect, useRef, useState } from 'react';
import { playPattern } from '../../audio/player.js';
import { createRecorder, recordFor } from '../../audio/recorder.js';
import Button from '../../components/Button.jsx';
import Field from '../../components/Field.jsx';
import LevelMeter from '../../components/LevelMeter.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import {
  LATENCY_BPM,
  LATENCY_CLICKS,
  NOISE_SECONDS,
  SENSITIVITY_SECONDS,
  clickTimesRelative,
  uploadStep,
} from './steps.js';
import styles from './CalibrationPage.module.css';

const STEPS = ['intro', 'noise', 'latency', 'sensitivity', 'save', 'done'];
const STEP_TITLES = {
  noise: 'Step 1 of 3: Listen to the quiet room',
  latency: 'Step 2 of 3: Tap along',
  sensitivity: 'Step 3 of 3: One soft hit, one loud hit',
  save: 'Save this setup',
};

export default function CalibrationPage() {
  useDocumentTitle('Room setup');
  const [step, setStep] = useState('intro');
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState({});
  const [label, setLabel] = useState('Activity room');
  const [profiles, setProfiles] = useState([]);
  const headingRef = useRef(null);

  useEffect(() => {
    api('/api/calibration')
      .then((d) => setProfiles(d.profiles))
      .catch(() => {});
  }, [step]);
  useEffect(() => headingRef.current?.focus(), [step]);

  const next = () => setStep(STEPS[STEPS.indexOf(step) + 1]);

  async function run(fn) {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setPrompt('');
      setLevel(0);
    }
  }

  const runNoise = () =>
    run(async () => {
      const take = await recordFor(NOISE_SECONDS, {
        onLevel: setLevel,
        onTick: (s) => setPrompt(`Please stay quiet… ${s}`),
      });
      setPrompt('Checking…');
      const r = await uploadStep('noise', take.wav);
      setResults((x) => ({ ...x, noise: r }));
    });

  const runLatency = () =>
    run(async () => {
      const rec = await createRecorder({ onLevel: setLevel });
      try {
        rec.start();
        let started;
        await playPattern({ events: [] }, LATENCY_BPM, {
          countIn: LATENCY_CLICKS,
          volume: 0.6,
          onStart: (s) => (started = s),
          onItem: (item) =>
            item.kind === 'count' && setPrompt(`Tap! (${LATENCY_CLICKS - item.index} left)`),
        });
        await new Promise((r) => setTimeout(r, 600));
        const take = await rec.stop();
        setPrompt('Checking…');
        const clicks = clickTimesRelative(started.startedAt, started.schedule, take.startTime);
        const r = await uploadStep('latency', take.wav, { click_times: clicks });
        setResults((x) => ({ ...x, latency: r }));
      } finally {
        rec.close();
      }
    });

  const runSensitivity = () =>
    run(async () => {
      const take = await recordFor(SENSITIVITY_SECONDS, {
        onLevel: setLevel,
        onTick: (s) => {
          const elapsed = SENSITIVITY_SECONDS - s;
          setPrompt(
            elapsed < 2
              ? 'Get ready…'
              : elapsed < 4
                ? 'Play ONE SOFT hit now'
                : 'Play ONE LOUD hit now',
          );
        },
      });
      setPrompt('Checking…');
      const r = await uploadStep('sensitivity', take.wav, {
        noise_floor_db: String(results.noise?.noise_floor_db ?? -60),
      });
      setResults((x) => ({ ...x, sensitivity: r }));
    });

  const save = () =>
    run(async () => {
      await api('/api/calibration', {
        method: 'POST',
        body: {
          device_label: label,
          latency_offset_ms: results.latency?.latency_offset_ms ?? 0,
          noise_floor_db: results.noise?.noise_floor_db ?? null,
          onset_threshold: results.sensitivity?.onset_threshold ?? 0.07,
        },
      });
      next();
    });

  const restart = () => {
    setResults({});
    setStep('noise');
  };

  const stepResult = {
    noise: results.noise,
    latency: results.latency,
    sensitivity: results.sensitivity,
  }[step];

  return (
    <>
      <h1>Room setup</h1>
      <p className={styles.lead}>
        This takes about one minute. It helps the app hear your drums clearly in this room. Do it
        once per room or laptop, or any time scores seem off.
      </p>
      <section className={styles.card} aria-labelledby="cal-step">
        <h2 id="cal-step" ref={headingRef} tabIndex={-1}>
          {STEP_TITLES[step] || (step === 'done' ? 'All set!' : 'Before you start')}
        </h2>
        {error && <Notice tone="error">{error}</Notice>}

        {step === 'intro' && (
          <>
            <p>You will need one drum. The microphone listens only during these steps.</p>
            <Button variant="primary" size="large" onClick={next}>
              Start room setup
            </Button>
          </>
        )}

        {step === 'noise' && (
          <p>
            Ask everyone to stay quiet for {NOISE_SECONDS} seconds while the app listens to the
            room.
          </p>
        )}
        {step === 'latency' && (
          <p>
            You will hear {LATENCY_CLICKS} clicks. Tap the drum{' '}
            <strong>exactly with each click</strong>.
          </p>
        )}
        {step === 'sensitivity' && (
          <p>When the screen says so, play one soft hit, then one loud hit.</p>
        )}

        {['noise', 'latency', 'sensitivity'].includes(step) && (
          <>
            {busy && (
              <>
                <p className={styles.prompt} aria-live="assertive">
                  {prompt}
                </p>
                <LevelMeter level={level} size="large" />
              </>
            )}
            {stepResult && !busy && (
              <Notice
                tone={
                  stepResult.ok === false || stepResult.reliable === false ? 'review' : 'success'
                }
              >
                {stepResult.message}
              </Notice>
            )}
            <div className={styles.row}>
              <Button
                variant={stepResult ? 'secondary' : 'primary'}
                size="large"
                disabled={busy}
                onClick={
                  { noise: runNoise, latency: runLatency, sensitivity: runSensitivity }[step]
                }
              >
                {busy ? 'Listening…' : stepResult ? 'Try again' : 'Start'}
              </Button>
              {stepResult && !busy && (
                <Button variant="primary" size="large" onClick={next}>
                  Next
                </Button>
              )}
            </div>
          </>
        )}

        {step === 'save' && (
          <>
            <dl className={styles.summary}>
              <dt>Room noise</dt>
              <dd>{results.noise?.message}</dd>
              <dt>Timing adjustment</dt>
              <dd>{Math.round(results.latency?.latency_offset_ms ?? 0)} milliseconds</dd>
              <dt>Sensitivity</dt>
              <dd>{results.sensitivity?.message}</dd>
            </dl>
            <Field
              label="Name for this room or laptop"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              maxLength={120}
            />
            <div className={styles.row}>
              <Button
                variant="primary"
                size="large"
                onClick={save}
                disabled={busy || !label.trim()}
              >
                Save setup
              </Button>
              <Button onClick={restart}>Start over</Button>
            </div>
          </>
        )}

        {step === 'done' && (
          <>
            <p>Saved. New classes will use this setup.</p>
            <Button onClick={restart}>Run setup again</Button>
          </>
        )}
      </section>

      {profiles.length > 0 && (
        <section aria-labelledby="saved-setups">
          <h2 id="saved-setups">Saved setups</h2>
          <ul>
            {profiles.map((p) => (
              <li key={p.id}>
                {p.device_label}: timing adjustment {Math.round(p.latency_offset_ms)} ms
                {p.created_at ? ` (saved ${new Date(p.created_at).toLocaleDateString()})` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
