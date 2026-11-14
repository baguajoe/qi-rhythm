import { measureMusicLevel, prepareMusic, runTurn } from './turnRunner.js';

const take = { wav: new Blob(['RIFF']), startTime: 100.0, sampleRate: 48000 };
const rec = { start: vi.fn(() => 100), stop: vi.fn(async () => take), close: vi.fn() };
vi.mock('../../audio/recorder.js', () => ({ createRecorder: vi.fn(async () => rec) }));
const musicHandle = { stop: vi.fn() };
const playPattern = vi.fn(async (_p, _bpm, opts) => {
  opts.onStart?.({ startedAt: 100.42, schedule: {} });
  if (opts.countIn) opts.onItem?.({ kind: 'count', countNumber: 4, index: 0 });
  return { startedAt: 100.42, music: opts.music ? musicHandle : null };
});
vi.mock('../../audio/player.js', () => ({ playPattern: (...a) => playPattern(...a) }));
const loadTrack = vi.fn(async (t) => ({ decoded: t.id }));
vi.mock('../../audio/music.js', async (orig) => ({
  ...(await orig()),
  loadTrack: (...a) => loadTrack(...a),
}));

const full = { id: 20, version: 'full', bpm: 90, loop_beats: 4, loop_seconds: 2.667 };
const bed = { id: 21, version: 'bed', bpm: 90, loop_beats: 4, loop_seconds: 2.667 };
const round = (music) => ({
  id: 5,
  reference: {
    pattern: { events: [{ beat: 0, voice: 'low' }] },
    bpm: 600,
    length_beats: 4,
    music,
  },
  capture: { count_in_beats: 4 },
});

function mockServer() {
  const sent = [];
  global.fetch = vi.fn(async (url, init) => {
    sent.push([init.method, url.replace(/^https?:\/\/[^/]+/, ''), init.body]);
    return { ok: true, status: 200, json: async () => ({ round: { id: 5 }, score: { id: 9 } }) };
  });
  return sent;
}

beforeEach(() => {
  playPattern.mockClear();
  musicHandle.stop.mockClear();
  loadTrack.mockClear();
});

test('full loop while listening, groove under the turn, music details uploaded', async () => {
  const sent = mockServer();
  await runTurn(round({ full, bed }), { volume: 0.7, musicVolume: 0.4 });
  const [listen, turn] = playPattern.mock.calls.map((c) => c[2]);
  expect(listen).toMatchObject({ muteHits: true, music: { track: full, volume: 0.4 } });
  expect(listen.music.buffer).toEqual({ decoded: 20 });
  expect(turn).toMatchObject({
    countIn: 4,
    playPattern: false,
    keepMusic: true,
    music: { track: bed, volume: 0.4, buffer: { decoded: 21 } },
  });
  expect(musicHandle.stop).toHaveBeenCalled(); // groove stops after the slack bar
  const form = sent.at(-1)[2];
  expect(form.get('backing_track_id')).toBe('21');
  expect(form.get('music_start_s')).toBe('0.42');
  expect(form.get('countin_start_s')).toBe('0.42');
  expect(form.get('music_volume')).toBe('0.4');
});

test('no music: built-in sounds and no music fields', async () => {
  const sent = mockServer();
  await runTurn(round(null));
  expect(playPattern.mock.calls.every((c) => c[2].music == null)).toBe(true);
  expect(sent.at(-1)[2].get('backing_track_id')).toBeNull();
});

test('music switched off or at zero volume is not played', async () => {
  for (const opts of [{ musicOn: false }, { musicVolume: 0 }]) {
    const sent = mockServer();
    await runTurn(round({ full, bed }), opts);
    expect(playPattern.mock.calls.every((c) => c[2].music == null)).toBe(true);
    expect(sent.at(-1)[2].get('backing_track_id')).toBeNull();
    playPattern.mockClear();
  }
  expect(loadTrack).not.toHaveBeenCalled();
});

test('a loop that fails to load falls back to the built-in sounds', async () => {
  const sent = mockServer();
  loadTrack.mockRejectedValue(new Error('offline'));
  const stages = [];
  await runTurn(round({ full, bed }), { emit: (s) => stages.push(s) });
  expect(stages).toContain('music-error');
  expect(playPattern.mock.calls[0][2]).toMatchObject({ music: null });
  expect(playPattern.mock.calls[0][2].muteHits).toBeFalsy();
  expect(sent.at(-1)[2].get('backing_track_id')).toBeNull();
  loadTrack.mockReset();
  loadTrack.mockImplementation(async (t) => ({ decoded: t.id }));
});

test('prepareMusic returns null for phases without a track', async () => {
  expect(await prepareMusic({ full, bed: null }, 'turn')).toBeNull();
});

test('measure music level plays the groove alone and uploads it', async () => {
  const sent = mockServer();
  await measureMusicLevel({ bed, bpm: 90, volume: 0.5, sessionId: 42 });
  const opts = playPattern.mock.calls[0][2];
  expect(opts).toMatchObject({ playPattern: false, lengthBeats: 12 }); // 3 loops x 4 beats
  expect(opts.keepMusic).toBeFalsy();
  expect(opts.music).toMatchObject({ track: bed, volume: 0.5 });
  const [method, path, form] = sent.at(-1);
  expect(`${method} ${path}`).toBe('POST /api/backing-tracks/21/bleed');
  expect(form.get('music_start_s')).toBe('0.42');
  expect(form.get('bpm')).toBe('90');
  expect(form.get('music_volume')).toBe('0.5');
  expect(form.get('session_id')).toBe('42');
  expect(rec.close).toHaveBeenCalled();
});
