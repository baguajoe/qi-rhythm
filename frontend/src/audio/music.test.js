import { chooseMusic, measureLoops, musicPlan } from './music.js';

const full = { id: 1, version: 'full', bpm: 90, loop_beats: 4, loop_seconds: 2.6667 };
const bed = { id: 2, version: 'bed', bpm: 90, loop_beats: 4, loop_seconds: 2.6667 };

test('listen plays the full loop with the synthesized pattern muted', () => {
  expect(chooseMusic({ full, bed }, 'listen')).toEqual({ track: full, muteHits: true });
});

test('listen with only a groove loop keeps the synthesized pattern audible', () => {
  expect(chooseMusic({ full: null, bed }, 'listen')).toEqual({ track: bed, muteHits: false });
});

test('the team turn only ever plays the groove-only loop', () => {
  expect(chooseMusic({ full, bed }, 'turn').track).toBe(bed);
  expect(chooseMusic({ full, bed: null }, 'turn')).toBeNull();
});

test('music off or no tracks falls back to the built-in sounds', () => {
  expect(chooseMusic({ full, bed }, 'listen', false)).toBeNull();
  expect(chooseMusic(null, 'listen')).toBeNull();
});

test('plays at the round tempo, time-stretching only when needed', () => {
  expect(musicPlan(bed, 90, 3)).toEqual({ rate: 1, stretch: false, loopEnd: 2.6667 });
  const slow = musicPlan(bed, 72, 3); // class speed 80%
  expect(slow.rate).toBeCloseTo(0.8);
  expect(slow.stretch).toBe(true);
  // A file a little shorter than bars x BPM never loops past its end.
  expect(musicPlan(bed, 90, 2.5).loopEnd).toBe(2.5);
});

test('measurement plays at least two loops and about 8 seconds', () => {
  expect(measureLoops(bed, 90)).toBe(3); // 2.67 s loops -> 3 loops = 8 s
  expect(measureLoops({ ...bed, loop_beats: 32 }, 90)).toBe(2); // 21 s loops
});
