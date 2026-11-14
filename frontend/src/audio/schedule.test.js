import {
  buildSchedule,
  effectiveBpm,
  patternLengthBeats,
  pickSurprise,
  recordingSeconds,
  sortedEvents,
} from './schedule.js';

const clave = {
  count_in_beats: 4,
  length_beats: 8,
  events: [
    { beat: 3, voice: 'high' },
    { beat: 0, voice: 'high', accent: true },
    { beat: 1.5, voice: 'high' },
    { beat: 5, voice: 'high' },
    { beat: 6, voice: 'high' },
  ],
};

test('effectiveBpm clamps tempo to 50-120%', () => {
  expect(effectiveBpm(100, 80)).toBe(80);
  expect(effectiveBpm(100, 200)).toBe(120);
  expect(effectiveBpm(90, 10)).toBe(45);
});

test('sortedEvents orders by beat and indexes', () => {
  const ev = sortedEvents(clave);
  expect(ev.map((e) => e.beat)).toEqual([0, 1.5, 3, 5, 6]);
  expect(ev.map((e) => e.index)).toEqual([0, 1, 2, 3, 4]);
});

test('buildSchedule places count-in then hits at beat times', () => {
  const s = buildSchedule(clave, 120, { countIn: 4 });
  const counts = s.items.filter((i) => i.kind === 'count');
  const hits = s.items.filter((i) => i.kind === 'hit');
  expect(counts.map((c) => c.countNumber)).toEqual([4, 3, 2, 1]);
  expect(counts.map((c) => c.time)).toEqual([0, 0.5, 1, 1.5]);
  expect(hits.map((h) => h.time)).toEqual([2, 2.75, 3.5, 4.5, 5]);
  expect(hits[0].accent).toBe(true);
  expect(s.patternStart).toBe(2);
  expect(s.duration).toBe(6);
});

test('pattern length falls back to whole bars', () => {
  expect(patternLengthBeats({ events: [{ beat: 5.5 }] })).toBe(8);
  expect(patternLengthBeats(clave)).toBe(8);
});

test('recordingSeconds covers count-in, pattern and one bar of slack', () => {
  expect(recordingSeconds(clave, 120)).toBe(8);
});

test('pickSurprise uses the random source', () => {
  expect(pickSurprise([1, 2, 3], () => 0.99)).toBe(3);
  expect(pickSurprise([], () => 0.5)).toBeNull();
});

test("the 'go' cue sits on the pattern's first beat, one beat after the final count", () => {
  const s = buildSchedule(clave, 90, { countIn: 4 });
  const spb = 60 / 90;
  const go = s.items.filter((i) => i.kind === 'go');
  const lastCount = s.items.filter((i) => i.kind === 'count').at(-1);
  expect(go).toHaveLength(1);
  expect(go[0].time).toBeCloseTo(4 * spb, 9);
  expect(go[0].time).toBeCloseTo(s.patternStart, 9);
  expect(go[0].time - lastCount.time).toBeCloseTo(spb, 9);
  // Same instant as a hit on beat 0, so the cue and the team's first note coincide.
  const firstHit = s.items.find((i) => i.kind === 'hit');
  expect(firstHit.time).toBeCloseTo(go[0].time, 9);
});

test("no 'go' cue without a count-in", () => {
  expect(buildSchedule(clave, 90).items.some((i) => i.kind === 'go')).toBe(false);
});
