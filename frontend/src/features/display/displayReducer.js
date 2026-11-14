// Pure state machine for the Display View, driven by Socket.IO events.

export const initialDisplayState = {
  status: 'connecting',
  phase: 'idle',
  settings: {},
  focus: null,
  reference: null,
  playedThrough: -1,
  count: null,
  level: 0,
  round: null,
  scoreboard: null,
};

function referenceFrom(payload) {
  if (!payload) return null;
  const ref = payload.reference || payload;
  return ref.pattern
    ? { ...ref, title: ref.title || payload.rhythm?.title, team: payload.team || ref.team }
    : null;
}

export function displayReducer(state, { type, payload = {} }) {
  switch (type) {
    case 'status':
      return { ...state, status: payload };
    case 'session:state': {
      const live = payload.live || {};
      return {
        ...state,
        phase: payload.ended ? 'ended' : live.phase || 'idle',
        settings: payload.settings || {},
        focus: live.focus || state.focus,
        reference: referenceFrom(live.reference) || referenceFrom(payload.round),
        count: live.count ?? null,
        round: payload.round,
        scoreboard: payload.scoreboard,
        playedThrough: -1,
        level: 0,
      };
    }
    case 'session:focus':
      return { ...state, focus: payload };
    case 'session:settings':
      return { ...state, settings: payload.settings || state.settings };
    case 'round:started':
      return {
        ...state,
        round: payload,
        reference: referenceFrom(payload),
        focus: { team: payload.team, rhythm: payload.rhythm },
        phase: 'ready',
        count: null,
        playedThrough: -1,
      };
    case 'round:reference_playing':
      return {
        ...state,
        phase: 'reference',
        reference: referenceFrom(payload) || state.reference,
        playedThrough: -1,
        count: null,
      };
    case 'round:beat':
      return { ...state, playedThrough: payload.index ?? state.playedThrough };
    case 'round:countin':
      return { ...state, phase: 'countin', count: payload.count ?? null, playedThrough: -1 };
    case 'round:recording':
      return { ...state, phase: 'recording', count: null, level: 0 };
    case 'round:level':
      return { ...state, level: payload.rms ?? 0 };
    case 'round:analyzing':
      return { ...state, phase: 'analyzing', level: 0 };
    case 'round:scored':
      return { ...state, phase: 'scored', round: payload };
    case 'round:overridden':
      return state.round && payload.id !== state.round.id
        ? state
        : { ...state, round: payload, phase: state.phase === 'scored' ? 'scored' : state.phase };
    case 'round:stopped':
    case 'round:failed':
    case 'session:idle':
      return { ...state, phase: 'idle', count: null, level: 0, playedThrough: -1 };
    case 'scoreboard:updated':
      return { ...state, scoreboard: payload };
    case 'session:ended':
      return { ...state, phase: 'ended', scoreboard: payload };
    default:
      return state;
  }
}
