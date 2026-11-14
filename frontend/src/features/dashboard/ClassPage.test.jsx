import { screen, within } from '@testing-library/react';
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
vi.mock('../game/turnRunner.js', () => ({ runTurn: (...a) => runTurn(...a) }));
vi.mock('../../audio/player.js', () => ({
  playPattern: vi.fn(async () => ({})),
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
