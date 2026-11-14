import { displayReducer, initialDisplayState } from './displayReducer.js';

const team = { id: 1, name: 'Sunflowers', color: '#b35900' };
const pattern = { events: [{ beat: 0, voice: 'low' }] };
const run = (events, state = initialDisplayState) =>
  events.reduce((s, [type, payload]) => displayReducer(s, { type, payload }), state);

test('follows a full turn', () => {
  const round = {
    id: 3,
    team,
    rhythm: { title: 'Son Clave' },
    reference: { pattern, bpm: 90, length_beats: 8 },
  };
  let s = run([
    ['status', 'connected'],
    ['round:started', round],
    ['round:reference_playing', round],
    ['round:beat', { index: 0 }],
  ]);
  expect(s.phase).toBe('reference');
  expect(s.playedThrough).toBe(0);
  expect(s.reference.title).toBe('Son Clave');
  s = run(
    [
      ['round:countin', { count: null }],
      ['round:countin', { count: 2 }],
    ],
    s,
  );
  expect(s).toMatchObject({ phase: 'countin', count: 2, playedThrough: -1 });
  s = run(
    [
      ['round:recording', {}],
      ['round:level', { rms: 0.3 }],
    ],
    s,
  );
  expect(s).toMatchObject({ phase: 'recording', level: 0.3, count: null });
  s = run(
    [
      ['round:analyzing', {}],
      ['round:scored', { ...round, score: { effective: { total: 88 } } }],
    ],
    s,
  );
  expect(s.phase).toBe('scored');
  expect(s.round.score.effective.total).toBe(88);
});

test('session:state snapshot restores everything after reconnect', () => {
  const s = run([
    ['round:countin', { count: 3 }],
    [
      'session:state',
      {
        settings: { high_contrast: true },
        live: { phase: 'scored', focus: { team } },
        round: { id: 9, team, score: {} },
        scoreboard: { teams: [] },
        ended: false,
      },
    ],
  ]);
  expect(s).toMatchObject({ phase: 'scored', count: null, settings: { high_contrast: true } });
  expect(s.focus.team.name).toBe('Sunflowers');
  expect(run([['session:state', { live: { phase: 'idle' }, ended: true }]]).phase).toBe('ended');
});

test('stop, override, settings and scoreboard', () => {
  let s = run([
    ['round:recording', {}],
    ['round:stopped', {}],
  ]);
  expect(s.phase).toBe('idle');
  s = run([
    ['round:scored', { id: 1, score: { effective: { total: 50 } } }],
    ['round:overridden', { id: 1, score: { effective: { total: 80 } } }],
  ]);
  expect(s.round.score.effective.total).toBe(80);
  s = run([['round:overridden', { id: 2, score: {} }]], s);
  expect(s.round.id).toBe(1);
  s = run(
    [
      ['session:settings', { settings: { cooperative_mode: true } }],
      ['scoreboard:updated', { teams: [1] }],
    ],
    s,
  );
  expect(s.settings.cooperative_mode).toBe(true);
  expect(s.scoreboard.teams).toEqual([1]);
  expect(run([['session:ended', { teams: [] }]]).phase).toBe('ended');
  expect(displayReducer(s, { type: 'unknown' })).toBe(s);
});
