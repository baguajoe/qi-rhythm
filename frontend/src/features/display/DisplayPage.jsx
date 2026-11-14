import { useEffect, useReducer, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import BeatVisualizer from '../../components/BeatVisualizer.jsx';
import LevelMeter from '../../components/LevelMeter.jsx';
import { api } from '../../lib/api.js';
import { textOn } from '../../lib/contrast.js';
import { messageFor, starsFor } from '../../lib/encouragement.js';
import { connectSession } from '../../lib/socket.js';
import { MASCOT_ICONS } from '../teams/teamStyle.js';
import { displayReducer, initialDisplayState } from './displayReducer.js';
import styles from './DisplayPage.module.css';

const tokenKey = (id) => `qi.display.${id}`;
const readToken = (id) => {
  try {
    return localStorage.getItem(tokenKey(id));
  } catch {
    return null;
  }
};
const writeToken = (id, t) => {
  try {
    if (t) localStorage.setItem(tokenKey(id), t);
    else localStorage.removeItem(tokenKey(id));
  } catch {
    /* ignore */
  }
};

function PairForm({ onPaired, sessionId, initialError }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState(initialError || '');
  async function submit(e) {
    e.preventDefault();
    try {
      const d = await api('/api/display/pair', { method: 'POST', body: { code } });
      if (String(d.session_id) !== String(sessionId))
        throw new Error('That code is for a different class.');
      onPaired(d.display_token);
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <main className={styles.pair}>
      <h1>Qi Rhythm</h1>
      <form onSubmit={submit}>
        <label htmlFor="code">Enter the code shown on the instructor&apos;s screen</label>
        <input
          id="code"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          maxLength={8}
          autoComplete="off"
          autoCapitalize="characters"
        />
        <button type="submit">Connect</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </main>
  );
}

function TeamTitle({ team, prefix }) {
  if (!team) return null;
  const icon = team.mascot_icon && MASCOT_ICONS[team.mascot_icon];
  return (
    <h1 className={styles.team} style={{ background: team.color, color: textOn(team.color) }}>
      {prefix && <span className={styles.prefix}>{prefix}</span>}
      {icon && (
        <span role="img" aria-label={icon.label}>
          {icon.emoji}{' '}
        </span>
      )}
      {team.name}
    </h1>
  );
}

function Leaderboard({ scoreboard }) {
  if (!scoreboard?.teams?.length) return null;
  if (scoreboard.cooperative) {
    return (
      <section className={styles.board} aria-label="Group total">
        <p className={styles.groupTotal}>Together: {Math.round(scoreboard.group_points)} points</p>
      </section>
    );
  }
  return (
    <section className={styles.board} aria-labelledby="board-h">
      <h2 id="board-h">Scoreboard</h2>
      <ol>
        {scoreboard.teams.map((row) => (
          <li key={row.team.id} style={{ borderColor: row.team.color }}>
            <span
              className={styles.swatch}
              style={{ background: row.team.color }}
              aria-hidden="true"
            />
            <span className={styles.boardName}>{row.team.name}</span>
            <span className={styles.boardPts}>{Math.round(row.points)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function CountIn({ count }) {
  const steps = [4, 3, 2, 1];
  return (
    <div className={styles.countin} aria-live="assertive">
      <p className={styles.huge}>{count ?? 'Get ready…'}</p>
      <p className={styles.countRow} aria-hidden="true">
        {steps.map((n) => (
          <span key={n} className={count !== null && n >= count ? styles.countOn : ''}>
            {n}
          </span>
        ))}
        <span>PLAY!</span>
      </p>
    </div>
  );
}

export function DisplayScreen({ state }) {
  const { phase, round, reference, focus, scoreboard } = state;
  const team =
    (['ready', 'reference', 'countin', 'recording', 'analyzing', 'scored'].includes(phase)
      ? round?.team
      : null) || focus?.team;
  const score = round?.score?.effective;

  return (
    <main className={styles.screen}>
      {state.status !== 'connected' && (
        <p className={styles.banner} role="status">
          {state.status === 'connecting' ? 'Connecting…' : 'Reconnecting…'}
        </p>
      )}
      {phase === 'ended' ? (
        <>
          <h1 className={styles.headline}>Thanks for playing!</h1>
          <Leaderboard scoreboard={scoreboard} />
        </>
      ) : (
        <>
          <TeamTitle team={team} prefix={phase === 'idle' ? 'Up next' : null} />
          {phase === 'idle' && (
            <>
              <p className={styles.headline}>
                {focus?.rhythm?.title ? `Rhythm: ${focus.rhythm.title}` : 'Get your drums ready!'}
              </p>
              <Leaderboard scoreboard={scoreboard} />
            </>
          )}
          {phase === 'ready' && <p className={styles.headline}>Get ready to listen…</p>}
          {phase === 'reference' && (
            <>
              <p className={styles.headline} aria-live="polite">
                👂 Listen to the pattern
              </p>
              {reference?.pattern && (
                <BeatVisualizer
                  pattern={reference.pattern}
                  lengthBeats={reference.length_beats}
                  playedThrough={state.playedThrough}
                  size="large"
                />
              )}
            </>
          )}
          {phase === 'countin' && <CountIn count={state.count} />}
          {phase === 'recording' && (
            <>
              <p className={`${styles.huge} ${styles.pulse}`} aria-live="assertive">
                Your turn!
              </p>
              <LevelMeter level={state.level} label="Drum sound" size="large" />
            </>
          )}
          {phase === 'analyzing' && (
            <p className={styles.headline} aria-live="polite">
              Listening back… 🎧
            </p>
          )}
          {phase === 'scored' && score && (
            <>
              <p
                className={styles.stars}
                role="img"
                aria-label={`${starsFor(score.total)} out of 5 stars`}
              >
                {'★'.repeat(starsFor(score.total))}
              </p>
              <p className={styles.points}>{Math.round(score.total)} points</p>
              <p className={styles.headline} aria-live="polite">
                {messageFor(score.total, round.id)}
              </p>
              <Leaderboard scoreboard={scoreboard} />
            </>
          )}
        </>
      )}
    </main>
  );
}

export default function DisplayPage() {
  const { sessionId } = useParams();
  const [params, setParams] = useSearchParams();
  const [token, setToken] = useState(() => readToken(sessionId));
  const [pairError, setPairError] = useState('');
  const [state, dispatch] = useReducer(displayReducer, initialDisplayState);

  // Auto-pair from ?code= (e.g. "Open TV screen" on the same laptop).
  useEffect(() => {
    const code = params.get('code');
    if (!code || token) return;
    api('/api/display/pair', { method: 'POST', body: { code } })
      .then((d) => {
        writeToken(sessionId, d.display_token);
        setToken(d.display_token);
        setParams({}, { replace: true });
      })
      .catch((e) => setPairError(e.message));
  }, [params, token, sessionId, setParams]);

  useEffect(() => {
    if (!token) return undefined;
    const socket = connectSession({
      token,
      sessionId: Number(sessionId),
      onEvent: (type, payload) => dispatch({ type, payload }),
      onStatus: (status) => {
        if (status === 'denied') {
          writeToken(sessionId, null);
          setToken(null);
          setPairError('This screen needs a new code from the instructor.');
        } else dispatch({ type: 'status', payload: status });
      },
    });
    return () => socket.disconnect();
  }, [token, sessionId]);

  useEffect(() => {
    document.documentElement.dataset.contrast = state.settings.high_contrast ? 'high' : 'normal';
    document.title = 'Qi Rhythm – Class screen';
  }, [state.settings.high_contrast]);

  if (!token) {
    return (
      <PairForm
        sessionId={sessionId}
        initialError={pairError}
        onPaired={(t) => {
          writeToken(sessionId, t);
          setToken(t);
        }}
      />
    );
  }
  return <DisplayScreen state={state} />;
}
