import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ME, renderApp } from '../../test/utils.jsx';
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
const LICENSE_WARNING =
  'Add the source and license notes before this track can be used in a class.';

function track(over) {
  return {
    rhythm_id: 3,
    version: 'bed',
    scope: 'organization',
    badge: null,
    bpm: 90,
    bars: 2,
    beats_per_bar: 4,
    loop_beats: 8,
    notes: '',
    original_filename: 'groove.wav',
    sample_rate: 44100,
    channels: 2,
    duration_s: 5.333,
    expected_duration_s: 5.333,
    source: 'original',
    license_notes: 'Mine',
    usable: true,
    warnings: [],
    audio_path: '/api/backing-tracks/0/audio',
    rev: 'a',
    ...over,
  };
}
const libraryBed = (over) =>
  track({
    id: 50,
    scope: 'library',
    badge: 'Qi Rhythm Original',
    notes: 'Eye Forge groove',
    ...over,
  });

/**
 * A tiny in-memory backend: tracks live in `db`, and the listing marks `in_use` / `can_edit`
 * with the server's rules (own usable loop beats the library's; only super-admins edit library).
 */
function fakeServer({ role = 'admin', tracks = [] } = {}) {
  const db = { tracks: [...tracks], forms: [], patches: [] };
  const me = { ...ME, instructor: { ...ME.instructor, role } };
  const view = () => {
    const inUse = {};
    for (const t of db.tracks.filter((x) => x.usable)) {
      const cur = inUse[t.version];
      if (!cur || (cur.scope === 'library' && t.scope !== 'library')) inUse[t.version] = t;
    }
    return db.tracks.map((t) => ({
      ...t,
      in_use: inUse[t.version]?.id === t.id,
      can_edit: t.scope === 'library' ? role === 'superadmin' : role !== 'instructor',
    }));
  };
  const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
  global.fetch = vi.fn(async (url, init = {}) => {
    const method = init.method || 'GET';
    const path = url.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
    if (path === '/api/auth/me') return json(me);
    if (path === '/api/genres') return json({ genres });
    if (path === '/api/rhythms') return json({ rhythms: [clave] });
    if (path === '/api/backing-tracks') return json({ tracks: view() });
    if (method === 'POST' && path === '/api/rhythms/3/backing-tracks') {
      const f = init.body;
      db.forms.push(f);
      const scope = f.get('scope');
      const t = track({
        id: 60 + db.forms.length,
        version: f.get('version'),
        scope,
        badge: scope === 'library' ? 'Qi Rhythm Original' : null,
        notes: f.get('notes'),
        duration_s: 5.9,
        source: f.get('source') || null,
        license_notes: f.get('license_notes'),
        usable: !!(f.get('source') && f.get('license_notes')),
        warnings: [
          'The file is 5.90 s long, but 2 bars at 90 BPM should be 5.33 s (longer by 0.57 s).',
          ...(f.get('source') && f.get('license_notes') ? [] : [LICENSE_WARNING]),
        ],
      });
      db.tracks = db.tracks.filter((x) => !(x.version === t.version && x.scope === scope));
      db.tracks.push(t);
      return json({ track: t }, 201);
    }
    const m = path.match(/^\/api\/backing-tracks\/(\d+)$/);
    if (m) {
      const id = Number(m[1]);
      if (method === 'DELETE') {
        db.tracks = db.tracks.filter((x) => x.id !== id);
        return json({ ok: true });
      }
      const body = JSON.parse(init.body);
      db.patches.push(body);
      db.tracks = db.tracks.map((x) =>
        x.id === id
          ? {
              ...x,
              ...body,
              usable: !!(body.source && body.license_notes),
              warnings: x.warnings.filter((w) => w !== LICENSE_WARNING),
            }
          : x,
      );
      return json({ track: db.tracks.find((x) => x.id === id) });
    }
    return json({ error: 'Not found.' }, 404);
  });
  return db;
}

async function openClave() {
  renderApp(<MusicPage />, { route: '/music' });
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
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
  const db = fakeServer();
  await openClave();
  expect(await screen.findByText(/No library loops for Son Clave 3-2 yet/)).toBeInTheDocument();
  expect(screen.getByText(/uses the built-in drum sounds/)).toBeInTheDocument();
  // Defaults come from the rhythm: 90 BPM, 8 beats = 2 bars of 4/4.
  expect(screen.getByRole('spinbutton', { name: 'BPM' })).toHaveValue(90);
  expect(screen.getByRole('spinbutton', { name: 'Bars' })).toHaveValue(2);
  expect(screen.getByText(/should be 5.33 s long/)).toBeInTheDocument();
  // Ordinary admins can't choose the library.
  expect(screen.queryByRole('group', { name: 'Add to' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Upload loop' }));
  expect(await screen.findByText('Please choose a WAV file to upload.')).toBeInTheDocument();

  const file = new File(['RIFF....WAVE'], 'groove.wav', { type: 'audio/wav' });
  await userEvent.upload(screen.getByLabelText('WAV file'), file);
  await userEvent.click(screen.getByLabelText(/Groove only/));
  await userEvent.type(screen.getByLabelText('Notes (optional)'), 'Dry mix');
  await userEvent.click(screen.getByRole('button', { name: 'Upload loop' }));

  expect(await screen.findByText('Uploaded the groove only loop.')).toBeInTheDocument();
  const form = db.forms[0];
  expect(form.get('version')).toBe('bed');
  expect(form.get('bpm')).toBe('90');
  expect(form.get('bars')).toBe('2');
  expect(form.get('notes')).toBe('Dry mix');
  expect(form.get('scope')).toBe('organization');
  expect(form.get('audio').name).toBe('groove.wav');

  const own = screen.getByRole('region', { name: /Your organization/ });
  const card = await within(own).findByRole('article', { name: /Groove only/ });
  expect(within(card).getByText('Not ready yet')).toBeInTheDocument();
  expect(within(card).getByText(/5.90 s long/)).toBeInTheDocument();
  expect(within(card).getByText(/doesn’t match/)).toBeInTheDocument();
  expect(within(card).getByText(/Add the source and license notes/)).toBeInTheDocument();
});

test('admin adds license info, then deletes the loop', async () => {
  const db = fakeServer({
    tracks: [track({ id: 21, source: null, license_notes: '', usable: false })],
  });
  await openClave();
  const card = await screen.findByRole('article', { name: /Groove only/ });
  await userEvent.selectOptions(
    within(card).getByLabelText('Where is this track from?'),
    'commissioned',
  );
  await userEvent.type(within(card).getByLabelText(/License notes/), 'Made for us by J. Doe');
  await userEvent.click(within(card).getByRole('button', { name: 'Save changes' }));
  expect(await within(card).findByText('Saved.')).toBeInTheDocument();
  expect(db.patches[0]).toMatchObject({
    source: 'commissioned',
    license_notes: 'Made for us by J. Doe',
  });
  expect(await within(card).findByText('Plays in your classes')).toBeInTheDocument();

  await userEvent.click(within(card).getByRole('button', { name: 'Delete…' }));
  await userEvent.click(within(card).getByRole('button', { name: 'Yes, delete this loop' }));
  expect(await screen.findByText(/uses the built-in drum sounds/)).toBeInTheDocument();
});

test('library loops show the badge, play for everyone, and are read-only for org admins', async () => {
  fakeServer({
    tracks: [
      libraryBed(),
      track({ id: 51, scope: 'library', badge: 'Qi Rhythm Original', version: 'full' }),
    ],
  });
  await openClave();
  const lib = await screen.findByRole('region', { name: 'Qi Rhythm Library' });
  const bed = await within(lib).findByRole('article', { name: /Groove only/ });
  expect(within(bed).getByText('★ Qi Rhythm Original')).toBeInTheDocument();
  expect(within(bed).getByText('Plays in your classes')).toBeInTheDocument();
  expect(within(bed).getByText('Eye Forge groove')).toBeInTheDocument();
  expect(within(bed).getByRole('button', { name: /Listen to this loop/ })).toBeInTheDocument();
  expect(within(lib).queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
  expect(within(lib).queryByRole('button', { name: 'Delete…' })).not.toBeInTheDocument();
  expect(screen.getByText(/Your classes use the library loops above/)).toBeInTheDocument();
});

test("an organization's own loop replaces the library's for that version", async () => {
  fakeServer({ tracks: [libraryBed(), track({ id: 21 })] });
  await openClave();
  const lib = await screen.findByRole('region', { name: 'Qi Rhythm Library' });
  expect(
    await within(lib).findByText('Not playing: your own loop is used instead'),
  ).toBeInTheDocument();
  const own = screen.getByRole('region', { name: /Your organization/ });
  expect(within(own).getByText('Plays in your classes')).toBeInTheDocument();
  expect(within(own).queryByText('★ Qi Rhythm Original')).not.toBeInTheDocument();
});

test('a super-admin can upload to the Qi Rhythm Library and edit library loops', async () => {
  const db = fakeServer({ role: 'superadmin', tracks: [libraryBed()] });
  await openClave();
  const lib = await screen.findByRole('region', { name: 'Qi Rhythm Library' });
  expect(await within(lib).findByRole('button', { name: 'Save changes' })).toBeInTheDocument();

  const target = screen.getByRole('group', { name: 'Add to' });
  await userEvent.click(within(target).getByLabelText(/Qi Rhythm Library/));
  await userEvent.upload(
    screen.getByLabelText('WAV file'),
    new File(['RIFF'], 'full.wav', { type: 'audio/wav' }),
  );
  await userEvent.selectOptions(
    screen.getAllByLabelText('Where is this track from?').at(-1),
    'original',
  );
  await userEvent.type(
    screen.getAllByLabelText(/License notes/).at(-1),
    'Eye Forge Studios original',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Upload loop' }));
  expect(
    await screen.findByText('Uploaded the full loop to the Qi Rhythm Library.'),
  ).toBeInTheDocument();
  expect(db.forms[0].get('scope')).toBe('library');
  expect(await within(lib).findByRole('article', { name: /^Full/ })).toBeInTheDocument();
});

test('non-admins can see loops but not change them', async () => {
  fakeServer({ role: 'instructor', tracks: [libraryBed(), track({ id: 21, version: 'full' })] });
  renderApp(<MusicPage />, { route: '/music' });
  expect(await screen.findByText(/Only an admin can add or change/)).toBeInTheDocument();
  await userEvent.selectOptions(await screen.findByLabelText('Rhythm'), '3');
  expect(await screen.findByRole('heading', { name: /Groove only/ })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /^Full/ })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Upload loop' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
});
