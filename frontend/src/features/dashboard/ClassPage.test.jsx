import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ClassPage from './ClassPage.jsx';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';

const machine = {
  pattern_accuracy: 100,
  timing_accuracy: 98,
  tempo_consistency: 100,
  completion: 100,
  total: 99,
};
const scoreObj = {
  id: 11,
  machine,
  effective: machine,
  confidence: 0.95,
  needs_review: false,
  review_reasons: [],
  confirmed: false,
  is_override: false,
  alignment: null,
};
const runTurn = vi.fn(async (round, { emit }) => {
  emit('reference');
  emit('countin', { countNumber: 4 });
  emit('recording');
  return { round: { ...round, team: { name: 'Sunflowers', color: '#b35900' } }, score: scoreObj };
});
const prepareMusic = vi.fn(async () => null);
const measureMusicLevel = vi.fn(async () => ({
  music_level: { created_at: '2026-11-14T10:00:00+00:00', music_volume: 0.6 },
  tone: 'success',
  message: 'Music level measured.',
}));
vi.mock('../game/turnRunner.js', () => ({
  runTurn: (...a) => runTurn(...a),
  prepareMusic: (...a) => prepareMusic(...a),
  measureMusicLevel: (...a) => measureMusicLevel(...a),
}));
vi.mock('../../audio/music.js', () => ({
  loadTrack: vi.fn(async () => ({})),
  setMusicVolume: vi.fn(),
}));
const sent = [];
vi.mock('./useSessionSocket.js', () => ({
  useSessionSocket: () => ({ status: 'connected', send: (e, p) => sent.push([e, p]) }),
}));
vi.mock('../../audio/player.js', () => ({
  playPattern: vi.fn(async (_p, _bpm, opts) => {
    opts?.onItem?.({ kind: 'hit', index: 0 });
    return {};
  }),
  stopPlayback: vi.fn(),
}));

const settings = {
  tolerance_preset: 'gentle',
  volume: 0.8,
  tempo_multiplier: 1,
  high_contrast: false,
  spoken_instructions: false,
  speech_rate: 0.9,
  cooperative_mode: false,
  auto_advance: false,
  music_volume: 0.6,
  music_on: true,
};
const teams = [
  { id: 1, name: 'Sunflowers', color: '#b35900', is_active: true, participants: [] },
  { id: 2, name: 'Blue Jays', color: '#1f4e99', is_active: true, participants: [] },
];
const clave = {
  id: 3,
  title: 'Son Clave 3-2',
  genre_slug: 'latin',
  difficulty: 'beginner',
  bpm: 90,
  length_beats: 8,
  pattern: { count_in_beats: 4, events: [{ beat: 0, voice: 'high' }] },
};
const sessionPayload = (rounds = [], board = []) => ({
  session: { id: 42, settings, ended_at: null },
  rounds,
  scoreboard: { teams: board, cooperative: false, group_points: 0 },
});

test('start class, run a turn, see score, confirm', async () => {
  let rounds = [];
  const calls = mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams },
    'GET /api/genres': {
      genres: [{ slug: 'latin', name: 'Latin', cultural_notes: 'Clave notes.' }],
    },
    'GET /api/rhythms': { rhythms: [clave] },
    'GET /api/calibration': { profiles: [{ id: 5, device_label: 'Activity room' }] },
    'GET /api/activities': { activities: [] },
    'POST /api/sessions': sessionPayload(),
    'GET /api/sessions/42': () =>
      sessionPayload(rounds, [{ team: teams[0], points: 99, turns: 1, best: 99 }]),
    'POST /api/sessions/42/rounds': () => {
      rounds = [{ id: 7 }];
      return { round: { id: 7, reference: {}, capture: {} } };
    },
    'POST /api/scores/11/confirm': { score: { ...scoreObj, confirmed: true } },
  });
  renderApp(<ClassPage />);
  expect(await screen.findByText(/microphone records the room/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Start class session/ }));
  expect(calls.find((c) => c.key === 'POST /api/sessions').body).toEqual({
    calibration_profile_id: 5,
  });

  const start = await screen.findByRole('button', { name: /Start team turn/ });
  expect(start).toBeDisabled();
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(start).toBeEnabled();
  await userEvent.click(start);

  expect(await screen.findByRole('heading', { name: 'Sunflowers: 99 points' })).toBeInTheDocument();
  expect(sent.map(([e]) => e)).toEqual(
    expect.arrayContaining(['control:focus', 'control:countin', 'control:recording']),
  );
  expect(sent.find(([e]) => e === 'control:countin')[1]).toEqual({ count: 4 });
  expect(calls.find((c) => c.key === 'POST /api/sessions/42/rounds').body).toEqual({
    rhythm_id: 3,
    team_id: 1,
  });
  await userEvent.click(screen.getByRole('button', { name: /Confirm score/ }));
  expect(await screen.findByText('✓ Score confirmed')).toBeInTheDocument();

  const board = await screen.findByRole('table');
  expect(within(board).getAllByText('99', { selector: 'td' })).toHaveLength(2);

  await userEvent.click(screen.getByRole('button', { name: /Next team/ }));
  expect(screen.getByRole('button', { name: /Blue Jays/ })).toHaveAttribute('aria-pressed', 'true');
});

test('changing the tolerance preset saves to the session', async () => {
  localStorage.setItem('qi.activeSession', '42');
  const calls = mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams },
    'GET /api/genres': { genres: [] },
    'GET /api/rhythms': { rhythms: [] },
    'GET /api/sessions/42': sessionPayload(),
    'GET /api/activities': { activities: [] },
    'PATCH /api/sessions/42': (req) => ({
      ...sessionPayload(),
      session: { id: 42, settings: { ...settings, ...req.body.settings } },
    }),
  });
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByLabelText(/Challenge/));
  expect(calls.find((c) => c.key === 'PATCH /api/sessions/42').body).toEqual({
    settings: { tolerance_preset: 'challenge' },
  });
});

test('playing the pattern tells the TV (reference, beats, then idle)', async () => {
  localStorage.setItem('qi.activeSession', '42');
  sent.length = 0;
  mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams },
    'GET /api/genres': { genres: [] },
    'GET /api/rhythms': { rhythms: [clave] },
    'GET /api/sessions/42': sessionPayload(),
    'GET /api/activities': { activities: [] },
  });
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  await userEvent.click(screen.getByRole('button', { name: /Play the pattern/ }));
  await screen.findByRole('button', { name: /Play again/ });
  const events = sent.map(([e]) => e).filter((e) => e !== 'control:focus');
  expect(events).toEqual(['control:reference', 'control:beat', 'control:idle']);
  expect(sent.find(([e]) => e === 'control:reference')[1]).toMatchObject({
    title: 'Son Clave 3-2',
    bpm: 90,
    length_beats: 8,
  });
});

const bedTrack = {
  id: 21,
  version: 'bed',
  usable: true,
  bpm: 90,
  loop_beats: 4,
  loop_seconds: 2.667,
  audio_path: '/api/backing-tracks/21/audio',
  music_level: null,
};
const fullTrack = {
  ...bedTrack,
  id: 20,
  version: 'full',
  audio_path: '/api/backing-tracks/20/audio',
};

function classWithTracks(tracks, extra = {}) {
  localStorage.setItem('qi.activeSession', '42');
  return mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams },
    'GET /api/genres': { genres: [] },
    'GET /api/rhythms': { rhythms: [clave] },
    'GET /api/sessions/42': sessionPayload(),
    'GET /api/activities': { activities: [] },
    'GET /api/backing-tracks': { tracks },
    ...extra,
  });
}

test('rhythms without loops use the built-in drums', async () => {
  classWithTracks([]);
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(await screen.findByText(/uses the built-in drum sounds/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Measure music level/ })).not.toBeInTheDocument();
});

test('unlicensed loops are not offered', async () => {
  classWithTracks([{ ...bedTrack, usable: false }]);
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(await screen.findByText(/uses the built-in drum sounds/)).toBeInTheDocument();
});

test('measure the music level, then a turn uses music settings', async () => {
  const calls = classWithTracks([fullTrack, bedTrack], {
    'POST /api/sessions/42/rounds': { round: { id: 7, reference: {}, capture: {} } },
  });
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(await screen.findByText(/Full version while listening, groove only/)).toBeInTheDocument();
  expect(
    screen.getByText(/Measure the music level once before the first turn/),
  ).toBeInTheDocument();
  expect(calls.some((c) => c.path === '/api/backing-tracks?rhythm_id=3')).toBe(true);

  await userEvent.click(screen.getByRole('button', { name: /Measure music level/ }));
  expect(measureMusicLevel).toHaveBeenCalledWith(
    expect.objectContaining({ bed: bedTrack, bpm: 90, volume: 0.6, sessionId: 42 }),
  );
  expect(await screen.findByText('Music level measured.')).toBeInTheDocument();
  expect(screen.getByText(/Music level measured Nov/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Start team turn/ }));
  await screen.findByRole('heading', { name: /Sunflowers/ });
  expect(runTurn.mock.calls.at(-1)[1]).toMatchObject({
    volume: 0.8,
    musicVolume: 0.6,
    musicOn: true,
  });
});

test('preview plays the full loop with the synthesized pattern muted', async () => {
  const { playPattern } = await import('../../audio/player.js');
  const listen = { track: fullTrack, buffer: {}, volume: 0.6, muteHits: true };
  prepareMusic.mockResolvedValueOnce(listen);
  classWithTracks([fullTrack]);
  renderApp(<ClassPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  await screen.findByText(/Full version while listening\. The turn uses the count-in only/);
  await userEvent.click(screen.getByRole('button', { name: /Play the pattern/ }));
  await screen.findByRole('button', { name: /Play again/ });
  expect(prepareMusic.mock.calls.at(-1)[1]).toBe('listen');
  expect(playPattern.mock.calls.at(-1)[2]).toMatchObject({ muteHits: true, music: listen });
});

test('music controls: separate volumes and an off switch', async () => {
  const calls = classWithTracks([bedTrack], {
    'PATCH /api/sessions/42': (req) => ({
      ...sessionPayload(),
      session: { id: 42, settings: { ...settings, ...req.body.settings } },
    }),
  });
  renderApp(<ClassPage />);
  expect(await screen.findByLabelText(/Pattern volume/)).toHaveValue('80');
  expect(screen.getByLabelText(/Music volume/)).toHaveValue('60');
  await userEvent.click(screen.getByRole('checkbox', { name: /Backing music/ }));
  expect(calls.find((c) => c.key === 'PATCH /api/sessions/42').body).toEqual({
    settings: { music_on: false },
  });
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(await screen.findByText(/Backing music is off/)).toBeInTheDocument();
});

test("starting a new turn hides the previous team's score until the new one arrives", async () => {
  const old = { id: 6, team: teams[1], score: { ...scoreObj, id: 10 } };
  let release;
  runTurn.mockImplementationOnce(
    (round) =>
      new Promise((resolve) => {
        release = () =>
          resolve({ round: { ...round, team: teams[0] }, score: { ...scoreObj, id: 12 } });
      }),
  );
  localStorage.setItem('qi.activeSession', '42');
  mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams },
    'GET /api/genres': { genres: [] },
    'GET /api/rhythms': { rhythms: [clave] },
    'GET /api/sessions/42': sessionPayload([old]),
    'GET /api/activities': { activities: [] },
    'POST /api/sessions/42/rounds': { round: { id: 7, reference: {}, capture: {} } },
  });
  renderApp(<ClassPage />);
  expect(await screen.findByRole('heading', { name: /Blue Jays: 99 points/ })).toBeInTheDocument();
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  await userEvent.click(screen.getByRole('button', { name: /Start team turn/ }));
  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: /Blue Jays: 99 points/ })).not.toBeInTheDocument(),
  );
  release();
  expect(await screen.findByRole('heading', { name: /Sunflowers: 99 points/ })).toBeInTheDocument();
});
