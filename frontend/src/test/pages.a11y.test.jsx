import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SettingsProvider } from '../app/settings.jsx';
import Layout from '../components/Layout.jsx';
import { AuthProvider } from '../features/auth/AuthContext.jsx';
import LoginPage from '../features/auth/LoginPage.jsx';
import CalibrationPage from '../features/calibration/CalibrationPage.jsx';
import ClassPage from '../features/dashboard/ClassPage.jsx';
import { DisplayScreen } from '../features/display/DisplayPage.jsx';
import { initialDisplayState } from '../features/display/displayReducer.js';
import ScorePanel from '../features/game/ScorePanel.jsx';
import LibraryPage from '../features/library/LibraryPage.jsx';
import MusicPage from '../features/music/MusicPage.jsx';
import TeamsPage from '../features/teams/TeamsPage.jsx';
import { axeViolations } from './axe.js';
import { ME, mockFetch } from './utils.jsx';

vi.mock('../audio/player.js', () => ({
  playPattern: vi.fn(async () => ({})),
  stopPlayback: vi.fn(),
}));
vi.mock('../features/dashboard/useSessionSocket.js', () => ({
  useSessionSocket: () => ({ status: 'connected', send: () => {} }),
}));

const team = {
  id: 1,
  name: 'Sunflowers',
  color: '#b35900',
  mascot_icon: 'sun',
  is_active: true,
  participants: [{ id: 1, alias: 'Rosie' }],
};
const team2 = {
  id: 2,
  name: 'Blue Jays',
  color: '#1f4e99',
  mascot_icon: null,
  is_active: true,
  participants: [],
};
const genres = [{ slug: 'latin', name: 'Latin', cultural_notes: 'Clave notes.' }];
const rhythm = {
  id: 3,
  title: 'Son Clave 3-2',
  genre_slug: 'latin',
  difficulty: 'beginner',
  bpm: 90,
  time_signature: '4/4',
  length_beats: 8,
  pattern: {
    count_in_beats: 4,
    events: [
      { beat: 0, voice: 'high' },
      { beat: 1.5, voice: 'clap' },
    ],
  },
};
const settings = {
  tolerance_preset: 'gentle',
  volume: 0.8,
  tempo_multiplier: 1,
  high_contrast: false,
  spoken_instructions: true,
  speech_rate: 0.9,
  cooperative_mode: false,
  auto_advance: false,
};
const machine = {
  pattern_accuracy: 80,
  timing_accuracy: 70,
  tempo_consistency: 90,
  completion: 100,
  total: 81,
};
const alignment = {
  expected: [
    { index: 0, beat: 0, voice: 'high', time_s: 3 },
    { index: 1, beat: 1.5, voice: 'clap', time_s: 4 },
  ],
  detected_s: [3.01, 4.6],
  matched: [
    { expected_index: 0, detected_index: 0, expected_s: 3, detected_s: 3.01, error_ms: 10 },
  ],
  missed: [1],
  extras: [1],
  global_offset_ms: 0,
  window_s: [2.5, 5],
};
const score = {
  id: 4,
  machine,
  effective: machine,
  confidence: 0.4,
  needs_review: true,
  review_reasons: ['Noisy'],
  confirmed: false,
  is_override: false,
  alignment,
};

const track = (over) => ({
  id: 20,
  rhythm_id: 3,
  version: 'full',
  bpm: 90,
  bars: 2,
  beats_per_bar: 4,
  loop_beats: 8,
  loop_seconds: 5.333,
  notes: 'Cubase export',
  original_filename: 'clave-full.wav',
  sample_rate: 48000,
  channels: 2,
  duration_s: 5.333,
  expected_duration_s: 5.333,
  source: 'original',
  license_notes: 'Recorded by me, 2026.',
  usable: true,
  warnings: [],
  music_level: null,
  audio_path: '/api/backing-tracks/20/audio',
  rev: '2026-11-14T00:00:00Z',
  ...over,
});
const tracks = [
  track({ scope: 'library', badge: 'Qi Rhythm Original', in_use: true, can_edit: false }),
  track({
    id: 21,
    version: 'bed',
    duration_s: 6.1,
    source: null,
    license_notes: '',
    usable: false,
    can_edit: true,
    warnings: [
      'The file is 6.10 s long, but 2 bars at 90 BPM should be 5.33 s.',
      'Add the source and license notes before this track can be used in a class.',
    ],
  }),
];

const ROUTES = {
  'GET /api/auth/me': ME,
  'GET /api/backing-tracks': { tracks },
  'GET /api/teams': { teams: [team, team2] },
  'GET /api/genres': { genres },
  'GET /api/rhythms': { rhythms: [rhythm] },
  'GET /api/calibration': {
    profiles: [
      { id: 1, device_label: 'Room', latency_offset_ms: 80, created_at: '2026-11-01T00:00:00Z' },
    ],
  },
  'GET /api/activities': { activities: [{ id: 1, name: 'Tuesday', rhythm_ids: [3] }] },
  'GET /api/sessions/42': {
    session: { id: 42, settings, ended_at: null },
    rounds: [{ id: 7, team, rhythm: { title: 'Son Clave 3-2' }, score }],
    scoreboard: {
      teams: [{ team, points: 81, turns: 1, best: 81 }],
      cooperative: false,
      group_points: 81,
    },
  },
};

function renderInLayout(page, path = '/') {
  localStorage.setItem('qi.token', 't');
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <SettingsProvider>
        <AuthProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="*" element={page} />
            </Route>
          </Routes>
        </AuthProvider>
      </SettingsProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => mockFetch(ROUTES));

test('login page has no axe violations', async () => {
  const { container } = render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SettingsProvider>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </SettingsProvider>
    </MemoryRouter>,
  );
  expect(await axeViolations(container)).toEqual([]);
  await userEvent.click(screen.getByRole('button', { name: /create an account/i }));
  expect(await axeViolations(container)).toEqual([]);
});

test('teams page', async () => {
  const { container } = renderInLayout(<TeamsPage />, '/teams');
  await screen.findByRole('button', { name: 'Remove Rosie' });
  expect(await axeViolations(container)).toEqual([]);
});

test('library page with a selected rhythm', async () => {
  const { container } = renderInLayout(<LibraryPage />, '/library');
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  expect(await axeViolations(container)).toEqual([]);
});

test('calibration page', async () => {
  const { container } = renderInLayout(<CalibrationPage />, '/calibration');
  await screen.findByText(/Room: timing adjustment/);
  expect(await axeViolations(container)).toEqual([]);
});

test('class page before and during a session', async () => {
  const { container, unmount } = renderInLayout(<ClassPage />);
  await screen.findByRole('button', { name: /Start class session/ });
  expect(await axeViolations(container)).toEqual([]);
  unmount();
  localStorage.setItem('qi.activeSession', '42');
  const view = renderInLayout(<ClassPage />);
  await screen.findByRole('heading', { name: 'Sunflowers: 81 points' });
  await userEvent.click(screen.getByRole('button', { name: /Son Clave 3-2/ }));
  await screen.findByText(/Full version while listening/); // backing music panel
  expect(await axeViolations(view.container)).toEqual([]);
  await userEvent.click(screen.getByRole('button', { name: 'Adjust score' }));
  expect(await axeViolations(view.container)).toEqual([]);
});

test('backing music page with tracks, warnings and the upload form', async () => {
  const { container } = renderInLayout(<MusicPage />, '/music');
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
  await screen.findByRole('heading', { name: /Groove only/ });
  expect(await axeViolations(container)).toEqual([]);
});

test('score panel', async () => {
  const { container } = render(
    <ScorePanel round={{ id: 1, team }} score={score} onConfirm={() => {}} onOverride={() => {}} />,
  );
  expect(await axeViolations(container, { isolated: true })).toEqual([]);
});

const displayStates = {
  idle: {
    phase: 'idle',
    focus: { team, rhythm: { title: 'Son Clave' } },
    scoreboard: {
      teams: [
        { team, points: 10 },
        { team: team2, points: 5 },
      ],
    },
  },
  reference: {
    phase: 'reference',
    round: { team },
    reference: { pattern: rhythm.pattern, length_beats: 8 },
    playedThrough: 1,
  },
  countin: { phase: 'countin', round: { team }, count: 2 },
  recording: { phase: 'recording', round: { team }, level: 0.2 },
  analyzing: { phase: 'analyzing', round: { team } },
  scored: {
    phase: 'scored',
    round: { id: 3, team, score: { effective: { total: 77 } } },
    scoreboard: { cooperative: true, group_points: 77, teams: [{ team, points: 77 }] },
  },
  ended: { phase: 'ended', scoreboard: { teams: [{ team, points: 10 }] } },
  reconnecting: { status: 'reconnecting', phase: 'idle' },
};

test.each(Object.entries(displayStates))('display view: %s', async (_name, patch) => {
  const { container } = render(
    <DisplayScreen state={{ ...initialDisplayState, status: 'connected', ...patch }} />,
  );
  expect(await axeViolations(container)).toEqual([]);
  // Display headlines are at least 48px (checked via the CSS clamp minimums).
});

test('sanity: axe does catch real problems', async () => {
  const { container } = render(
    <main>
      <button type="button" />
      {/* eslint-disable-next-line jsx-a11y/alt-text -- deliberately broken markup for the sanity check */}
      <img src="x.png" />
      <input type="text" />
    </main>,
  );
  const v = await axeViolations(container);
  expect(v.join('\n')).toMatch(/button-name/);
  expect(v.join('\n')).toMatch(/image-alt/);
  expect(v.join('\n')).toMatch(/label/);
});
