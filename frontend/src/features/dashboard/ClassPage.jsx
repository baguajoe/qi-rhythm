import { useEffect, useMemo, useRef, useState } from 'react';
import { effectiveBpm } from '../../audio/schedule.js';
import { speak } from '../../audio/speech.js';
import { stopPlayback } from '../../audio/player.js';
import { usePatternPlayer } from '../../audio/usePatternPlayer.js';
import BeatVisualizer from '../../components/BeatVisualizer.jsx';
import Button from '../../components/Button.jsx';
import LevelMeter from '../../components/LevelMeter.jsx';
import Notice from '../../components/Notice.jsx';
import { api } from '../../lib/api.js';
import { messageFor } from '../../lib/encouragement.js';
import ScorePanel from '../game/ScorePanel.jsx';
import { runTurn } from '../game/turnRunner.js';
import RhythmPicker from '../library/RhythmPicker.jsx';
import { useLibrary } from '../library/useLibrary.js';
import TeamBadge from '../teams/TeamBadge.jsx';
import Scoreboard from './Scoreboard.jsx';
import SessionSettings from './SessionSettings.jsx';
import StartClass from './StartClass.jsx';
import { useClassSession } from './useClassSession.js';
import styles from './ClassPage.module.css';

const PHASE_TEXT = {
  idle: 'Ready when you are.',
  preview: 'Playing the pattern…',
  reference: 'Listen to the pattern…',
  countin: 'Get ready…',
  recording: 'Your turn! Play the pattern.',
  uploading: 'Listening back…',
  waiting:
    'Waiting for the internet connection. The recording is saved and will be sent automatically.',
  scored: 'Here is the score.',
  error: 'Something went wrong.',
};

export default function ClassPage() {
  const cls = useClassSession();
  const { genres, rhythms } = useLibrary();
  const [teams, setTeams] = useState([]);
  const [rhythm, setRhythm] = useState(null);
  const [teamId, setTeamId] = useState(null);
  const [phase, setPhase] = useState('idle');
  const [count, setCount] = useState(null);
  const [playedThrough, setPlayedThrough] = useState(-1);
  const [level, setLevel] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const abortRef = useRef(null);
  const preview = usePatternPlayer();

  useEffect(() => {
    api('/api/teams')
      .then((d) => {
        setTeams(d.teams);
        setTeamId((id) => id ?? d.teams[0]?.id ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);

  const settings = cls.data?.session.settings;
  const team = teams.find((t) => t.id === teamId);
  const bpm = rhythm && settings ? effectiveBpm(rhythm.bpm, settings.tempo_multiplier * 100) : null;
  const busy = !['idle', 'scored', 'error'].includes(phase) || preview.playing;
  const say = (text) =>
    speak(text, { enabled: settings?.spoken_instructions, rate: settings?.speech_rate });

  // Restore the most recent turn's score when returning to the page.
  useEffect(() => {
    if (!cls.data || result) return;
    const last = [...cls.data.rounds].reverse().find((r) => r.score);
    if (last) setResult({ round: last, score: last.score });
  }, [cls.data, result]);

  const genre = useMemo(() => genres.find((g) => g.slug === rhythm?.genre_slug), [genres, rhythm]);

  if (!cls.sessionId || !cls.data) {
    return (
      <>
        <h1>Class</h1>
        {cls.error && <Notice tone="error">{cls.error}</Notice>}
        <StartClass onStart={cls.start} />
      </>
    );
  }

  async function playPreview() {
    setError('');
    say('Listen to the pattern.');
    setPhase('preview');
    await preview.play(rhythm.pattern, bpm, {
      lengthBeats: rhythm.length_beats,
      volume: settings.volume,
    });
    setPhase('idle');
  }

  async function startTurn() {
    setError('');
    setResult(null);
    setPlayedThrough(-1);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const { round } = await api(`/api/sessions/${cls.sessionId}/rounds`, {
        method: 'POST',
        body: { rhythm_id: rhythm.id, team_id: team.id },
      });
      say(`${team.name}, listen to the pattern.`);
      const res = await runTurn(round, {
        volume: settings.volume,
        signal: controller.signal,
        emit: (stage, data) => {
          if (stage === 'reference') setPhase('reference');
          else if (stage === 'hit') setPlayedThrough(data.index);
          else if (stage === 'countin') {
            setPhase('countin');
            setPlayedThrough(-1);
            setCount(data.countNumber);
          } else if (stage === 'recording') {
            setCount(null);
            setPhase('recording');
          } else if (stage === 'level') setLevel(data);
          else if (stage === 'uploading') setPhase('uploading');
          else if (stage === 'waiting') setPhase('waiting');
        },
      });
      setResult(res);
      setPhase('scored');
      say(messageFor(res.score.effective.total, res.round.id));
      cls.refresh();
    } catch (e) {
      if (e.name === 'AbortError') {
        setPhase('idle');
        setNotice('Stopped. You can start the turn again when ready.');
      } else {
        setPhase('error');
        setError(e.message);
      }
    } finally {
      abortRef.current = null;
      setCount(null);
      setLevel(0);
    }
  }

  function stop() {
    abortRef.current?.abort();
    preview.stop();
    stopPlayback();
    setPhase('idle');
  }

  function nextTeam() {
    const active = teams.filter((t) => t.is_active);
    const i = active.findIndex((t) => t.id === teamId);
    setTeamId(active[(i + 1) % active.length]?.id ?? null);
    setResult(null);
    setPhase('idle');
  }

  async function confirm() {
    const { score } = await api(`/api/scores/${result.score.id}/confirm`, { method: 'POST' });
    setResult((r) => ({ ...r, score }));
    if (settings.auto_advance) nextTeam();
  }

  async function override(body) {
    const res = await api(`/api/scores/${result.score.id}/override`, { method: 'POST', body });
    setResult(res);
    cls.refresh();
  }

  async function endClass() {
    stop();
    await cls.end();
    setResult(null);
  }

  async function deleteRecordings() {
    const { deleted } = await api('/api/recordings/purge', { method: 'POST' });
    setNotice(
      deleted
        ? `Deleted ${deleted} recording${deleted === 1 ? '' : 's'}.`
        : 'There were no recordings to delete.',
    );
  }

  const canStart = rhythm && team && !busy;
  const visPlayed =
    phase === 'reference' || phase === 'preview'
      ? preview.playing
        ? preview.playedThrough
        : playedThrough
      : -1;

  return (
    <>
      <h1>Class in progress</h1>
      {error && <Notice tone="error">{error}</Notice>}
      {notice && <Notice tone="info">{notice}</Notice>}

      <div className={styles.grid}>
        <section className={styles.card} aria-labelledby="pick-title">
          <h2 id="pick-title">1. Choose a rhythm</h2>
          <RhythmPicker
            genres={genres}
            rhythms={rhythms}
            selectedId={rhythm?.id}
            onSelect={(r) => r && setRhythm(r)}
          />
        </section>

        <div className={styles.column}>
          <section className={styles.card} aria-labelledby="team-title">
            <h2 id="team-title">2. Whose turn?</h2>
            {teams.length < 2 && <p>Tip: make at least two teams on the Teams page.</p>}
            <div className={styles.teamButtons} role="group" aria-labelledby="team-title">
              {teams.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`${styles.teamButton} ${t.id === teamId ? styles.teamOn : ''}`}
                  aria-pressed={t.id === teamId}
                  onClick={() => setTeamId(t.id)}
                  disabled={busy}
                >
                  <TeamBadge team={t} size="large" />
                </button>
              ))}
            </div>
          </section>

          <section className={`${styles.card} ${styles.stage}`} aria-labelledby="play-title">
            <h2 id="play-title">3. Play</h2>
            {rhythm ? (
              <p className={styles.now}>
                <strong>{rhythm.title}</strong> · {Math.round(bpm)} bpm{' '}
                {team && (
                  <>
                    · <TeamBadge team={team} />
                  </>
                )}
              </p>
            ) : (
              <p>Choose a rhythm first.</p>
            )}
            {rhythm && (
              <BeatVisualizer
                pattern={rhythm.pattern}
                lengthBeats={rhythm.length_beats}
                playedThrough={visPlayed}
              />
            )}
            <p className={styles.phase} aria-live="polite">
              {count ? <span className={styles.count}>{count}</span> : PHASE_TEXT[phase]}
            </p>
            {phase === 'recording' && (
              <LevelMeter level={level} label="Sound level in the room" size="large" />
            )}
            <div className={styles.controls}>
              <Button
                variant="secondary"
                size="huge"
                onClick={playPreview}
                disabled={!rhythm || busy}
              >
                {result || preview.playedThrough > -1 ? '↻ Play again' : '▶ Play the pattern'}
              </Button>
              <Button variant="primary" size="huge" onClick={startTurn} disabled={!canStart}>
                🥁 Start team turn
              </Button>
              <Button variant="danger" size="huge" onClick={stop} disabled={!busy}>
                ■ Stop
              </Button>
              <Button size="huge" onClick={nextTeam} disabled={busy || teams.length < 2}>
                Next team →
              </Button>
            </div>
          </section>

          {result && (
            <ScorePanel
              round={result.round}
              score={result.score}
              onConfirm={confirm}
              onOverride={override}
            />
          )}
          <Scoreboard scoreboard={cls.data.scoreboard} />
        </div>
      </div>

      <SessionSettings settings={settings} onChange={cls.updateSettings} baseBpm={rhythm?.bpm} />
      {genre?.cultural_notes && (
        <section className={styles.card} aria-labelledby="about-title">
          <h2 id="about-title">About {genre.name}</h2>
          <p>{genre.cultural_notes}</p>
        </section>
      )}
      <section className={styles.card} aria-labelledby="finish-title">
        <h2 id="finish-title">Finish</h2>
        <div className={styles.controls}>
          <Button onClick={deleteRecordings}>Delete recordings now</Button>
          <Button variant="danger" onClick={endClass}>
            End class
          </Button>
        </div>
      </section>
    </>
  );
}
