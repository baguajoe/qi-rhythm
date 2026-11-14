import { CATEGORY_LABELS, confidenceLevel, messageFor, starsFor } from './encouragement.js';

test('stars never drop below one', () => {
  expect(starsFor(0)).toBe(1);
  expect(starsFor(29.9)).toBe(1);
  expect(starsFor(30)).toBe(2);
  expect(starsFor(95)).toBe(5);
});

test('messages are never shaming', () => {
  const banned = /fail|wrong|bad|poor|lose|loser|terrible/i;
  for (let total = 0; total <= 100; total += 5) {
    for (let seed = 0; seed < 3; seed += 1) {
      const m = messageFor(total, seed);
      expect(m).toBeTruthy();
      expect(m).not.toMatch(banned);
    }
  }
});

test('labels use plain language', () => {
  expect(Object.values(CATEGORY_LABELS)).toEqual([
    'Right hits',
    'On the beat',
    'Steady speed',
    'Played it all',
  ]);
});

test('confidence levels', () => {
  expect(confidenceLevel(0.9).key).toBe('high');
  expect(confidenceLevel(0.6).key).toBe('medium');
  expect(confidenceLevel(0.1).label).toBe('Unclear recording');
});
