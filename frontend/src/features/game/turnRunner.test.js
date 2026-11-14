import { countinStartSeconds, runTurn } from './turnRunner.js';

const take = { wav: new Blob(['RIFF']), startTime: 100.0, sampleRate: 48000 };
const rec = { start: vi.fn(() => 100), stop: vi.fn(async () => take), close: vi.fn() };
vi.mock('../../audio/recorder.js', () => ({ createRecorder: vi.fn(async () => rec) }));
vi.mock('../../audio/player.js', () => ({
  playPattern: vi.fn(async (_p, _bpm, opts) => {
    opts.onStart?.({ startedAt: 100.42, schedule: {} });
    if (opts.countIn) opts.onItem?.({ kind: 'count', countNumber: 4, index: 0 });
    else opts.onItem?.({ kind: 'hit', index: 0 });
    return { startedAt: 100.42 };
  }),
}));

const round = {
  id: 5,
  reference: { pattern: { events: [{ beat: 0, voice: 'low' }] }, bpm: 600, length_beats: 4 },
  capture: { count_in_beats: 4 },
};

test('countinStartSeconds', () => {
  expect(countinStartSeconds(100.42, 100.0)).toBeCloseTo(0.42, 5);
});

test('runs reference, count-in, recording, upload in order', async () => {
  const sent = [];
  global.fetch = vi.fn(async (url, init) => {
    sent.push([init.method, url.replace(/^https?:\/\/[^/]+/, ''), init.body]);
    return { ok: true, status: 200, json: async () => ({ round: { id: 5 }, score: { id: 9 } }) };
  });
  const stages = [];
  const res = await runTurn(round, { emit: (s) => stages.push(s) });
  expect(res.score.id).toBe(9);
  expect(sent.map(([m, p]) => `${m} ${p}`)).toEqual([
    'PATCH /api/rounds/5',
    'PATCH /api/rounds/5',
    'POST /api/rounds/5/recording',
  ]);
  expect(JSON.parse(sent[0][2])).toEqual({ status: 'playing_reference' });
  expect(JSON.parse(sent[1][2])).toEqual({ status: 'recording' });
  const form = sent[2][2];
  expect(form.get('countin_start_s')).toBe('0.42');
  expect(stages).toEqual(['reference', 'hit', 'countin', 'recording', 'uploading', 'scored']);
  expect(rec.close).toHaveBeenCalled();
});

test('can skip the reference playback', async () => {
  global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ score: {} }) }));
  const stages = [];
  await runTurn(round, { playReference: false, emit: (s) => stages.push(s) });
  expect(stages[0]).toBe('countin');
});

test('"Your turn" (recording) is emitted on the go cue, not when playback ends', async () => {
  const { playPattern } = await import('../../audio/player.js');
  let finishPlayback;
  const stages = [];
  playPattern.mockImplementationOnce(async (_p, _bpm, opts) => opts.onItem?.({ kind: 'hit' }));
  playPattern.mockImplementationOnce((_p, _bpm, opts) => {
    opts.onStart?.({ startedAt: 100.42, schedule: {} });
    for (const n of [4, 3, 2, 1]) opts.onItem?.({ kind: 'count', countNumber: n, index: 4 - n });
    opts.onItem?.({ kind: 'go', index: -1 });
    // The pattern's length still has to play out while the team plays.
    return new Promise((resolve) => (finishPlayback = () => resolve({ startedAt: 100.42 })));
  });
  global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ score: {} }) }));
  const done = runTurn(round, { emit: (s, d) => stages.push(d?.countNumber ?? s) });
  await vi.waitFor(() => expect(finishPlayback).toBeDefined());
  // Playback hasn't finished, yet the team has been told to play right after "1".
  expect(stages).toEqual(['reference', 'hit', 4, 3, 2, 1, 'recording']);
  finishPlayback();
  await done;
  expect(stages.filter((s) => s === 'recording')).toHaveLength(1);
});
