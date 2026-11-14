import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CalibrationPage from './CalibrationPage.jsx';
import { clickTimesRelative } from './steps.js';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';

const fakeTake = { wav: new Blob(['x'.repeat(2000)]), startTime: 10.0, sampleRate: 48000 };
vi.mock('../../audio/recorder.js', () => ({
  recordFor: vi.fn(async () => fakeTake),
  createRecorder: vi.fn(async () => ({
    start: () => 10,
    stop: async () => fakeTake,
    close: () => {},
  })),
}));
vi.mock('../../audio/player.js', () => ({
  playPattern: vi.fn(async (_p, _bpm, opts) => {
    opts.onStart?.({
      startedAt: 10.5,
      schedule: {
        items: [
          { kind: 'count', time: 0 },
          { kind: 'count', time: 0.75 },
        ],
      },
    });
    return { startedAt: 10.5 };
  }),
}));

test('clickTimesRelative converts AudioContext times to recording times', () => {
  const sched = {
    items: [
      { kind: 'count', time: 0 },
      { kind: 'count', time: 0.75 },
      { kind: 'hit', time: 2 },
    ],
  };
  expect(clickTimesRelative(10.5, sched, 10.0)).toEqual([0.5, 1.25]);
});

test('walks through all steps and saves a profile', async () => {
  const calls = mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/calibration': { profiles: [] },
    'POST /api/calibration/analyze/noise': {
      noise_floor_db: -52,
      message: 'The room is nice and quiet.',
    },
    'POST /api/calibration/analyze/latency': {
      latency_offset_ms: 92,
      reliable: true,
      message: 'Got it.',
    },
    'POST /api/calibration/analyze/sensitivity': {
      onset_threshold: 0.05,
      ok: true,
      message: 'Sounds good.',
    },
    'POST /api/calibration': (req) => ({ profile: { id: 1, ...req.body } }),
  });
  // FormData bodies are not JSON; patch the mock to skip parsing for them.
  const orig = global.fetch;
  global.fetch = vi.fn((url, init = {}) =>
    init.body instanceof FormData ? orig(url, { ...init, body: undefined }) : orig(url, init),
  );

  renderApp(<CalibrationPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Start room setup' }));
  for (const expected of ['nice and quiet', 'Got it.', 'Sounds good.']) {
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(await screen.findByText(new RegExp(expected))).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  }
  expect(screen.getByText('92 milliseconds')).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText('Name for this room or laptop'));
  await userEvent.type(screen.getByLabelText('Name for this room or laptop'), 'Dining hall');
  await userEvent.click(screen.getByRole('button', { name: 'Save setup' }));
  expect(await screen.findByRole('heading', { name: 'All set!' })).toBeInTheDocument();
  const saved = calls.find((c) => c.key === 'POST /api/calibration');
  expect(saved.body).toEqual({
    device_label: 'Dining hall',
    latency_offset_ms: 92,
    noise_floor_db: -52,
    onset_threshold: 0.05,
  });
});
