import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';
import MusicPage, { beatsPerBar, expectedSeconds } from './MusicPage.jsx';

const genres = [{ slug: 'latin', name: 'Latin' }];
const clave = {
  id: 3,
  title: 'Son Clave 3-2',
  genre_slug: 'latin',
  bpm: 90,
  length_beats: 8,
  time_signature: '4/4',
};
const uploaded = {
  id: 21,
  rhythm_id: 3,
  version: 'bed',
  bpm: 90,
  bars: 2,
  beats_per_bar: 4,
  loop_beats: 8,
  notes: '',
  original_filename: 'groove.wav',
  sample_rate: 44100,
  channels: 2,
  duration_s: 5.9,
  expected_duration_s: 5.333,
  source: null,
  license_notes: '',
  usable: false,
  warnings: [
    'The file is 5.90 s long, but 2 bars at 90 BPM should be 5.33 s (longer by 0.57 s).',
    'Add the source and license notes before this track can be used in a class.',
  ],
  audio_path: '/api/backing-tracks/21/audio',
  rev: 'a',
};

function routes(extra = {}) {
  return mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/genres': { genres },
    'GET /api/rhythms': { rhythms: [clave] },
    'GET /api/backing-tracks': { tracks: [] },
    ...extra,
  });
}

test('beats per bar and expected length', () => {
  expect(beatsPerBar('4/4')).toBe(4);
  expect(beatsPerBar('12/8')).toBe(4);
  expect(beatsPerBar('6/8')).toBe(2);
  expect(beatsPerBar('3/4')).toBe(3);
  expect(expectedSeconds(90, 2, 4)).toBeCloseTo(5.333, 3);
  expect(expectedSeconds('', 2, 4)).toBeNull();
});

test('admin uploads a groove loop and sees the length check and license reminder', async () => {
  let sentForm = null;
  routes({
    'POST /api/rhythms/3/backing-tracks': () => ({ track: uploaded }),
  });
  const realFetch = global.fetch;
  global.fetch = vi.fn((url, init = {}) => {
    if (init.body instanceof FormData) sentForm = init.body;
    return realFetch(url, { ...init, body: init.body instanceof FormData ? undefined : init.body });
  });
  renderApp(<MusicPage />, { route: '/music' });
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
  expect(await screen.findByText(/No loops yet/)).toBeInTheDocument();
  // Defaults come from the rhythm: 90 BPM, 8 beats = 2 bars of 4/4.
  expect(screen.getByRole('spinbutton', { name: 'BPM' })).toHaveValue(90);
  expect(screen.getByRole('spinbutton', { name: 'Bars' })).toHaveValue(2);
  expect(screen.getByText(/should be 5.33 s long/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Upload loop' }));
  expect(await screen.findByText('Please choose a WAV file to upload.')).toBeInTheDocument();

  const file = new File(['RIFF....WAVE'], 'groove.wav', { type: 'audio/wav' });
  await userEvent.upload(screen.getByLabelText('WAV file'), file);
  await userEvent.click(screen.getByLabelText(/Groove only/));
  await userEvent.type(screen.getByLabelText('Notes (optional)'), 'Dry mix');
  await userEvent.click(screen.getByRole('button', { name: 'Upload loop' }));

  expect(await screen.findByText('Uploaded the groove only loop.')).toBeInTheDocument();
  expect(sentForm.get('version')).toBe('bed');
  expect(sentForm.get('bpm')).toBe('90');
  expect(sentForm.get('bars')).toBe('2');
  expect(sentForm.get('notes')).toBe('Dry mix');
  expect(sentForm.get('audio').name).toBe('groove.wav');

  const card = screen.getByRole('article', { name: /Groove only/ });
  expect(within(card).getByText('Not ready yet')).toBeInTheDocument();
  expect(within(card).getByText(/5.90 s long/)).toBeInTheDocument();
  expect(within(card).getByText(/doesn’t match/)).toBeInTheDocument();
  expect(within(card).getByText(/Add the source and license notes/)).toBeInTheDocument();
});

test('admin adds license info, then deletes the loop', async () => {
  const calls = routes({
    'GET /api/backing-tracks': { tracks: [uploaded] },
    'PATCH /api/backing-tracks/21': (req) => ({
      track: { ...uploaded, ...req.body, usable: true, warnings: [uploaded.warnings[0]] },
    }),
    'DELETE /api/backing-tracks/21': { ok: true },
  });
  renderApp(<MusicPage />, { route: '/music' });
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
  const card = await screen.findByRole('article', { name: /Groove only/ });
  await userEvent.selectOptions(
    within(card).getByLabelText('Where is this track from?'),
    'commissioned',
  );
  await userEvent.type(within(card).getByLabelText(/License notes/), 'Made for us by J. Doe');
  await userEvent.click(within(card).getByRole('button', { name: 'Save changes' }));
  expect(await within(card).findByText('Saved.')).toBeInTheDocument();
  expect(calls.find((c) => c.key === 'PATCH /api/backing-tracks/21').body).toMatchObject({
    source: 'commissioned',
    license_notes: 'Made for us by J. Doe',
  });
  expect(within(card).getByText('Ready for classes')).toBeInTheDocument();

  await userEvent.click(within(card).getByRole('button', { name: 'Delete…' }));
  await userEvent.click(within(card).getByRole('button', { name: 'Yes, delete this loop' }));
  expect(await screen.findByText(/No loops yet/)).toBeInTheDocument();
});

test('non-admins can see loops but not change them', async () => {
  routes({
    'GET /api/auth/me': { ...ME, instructor: { ...ME.instructor, role: 'instructor' } },
    'GET /api/backing-tracks': { tracks: [uploaded] },
  });
  renderApp(<MusicPage />, { route: '/music' });
  expect(await screen.findByText(/Only an admin can add or change/)).toBeInTheDocument();
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
  expect(await screen.findByRole('heading', { name: 'Groove only' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Upload loop' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
});
