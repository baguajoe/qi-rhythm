import { contrastRatio, textOn } from './contrast.js';
import { TEAM_COLORS } from '../features/teams/teamStyle.js';

test('contrast ratio of black on white is 21', () => {
  expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 1);
});

test.each(TEAM_COLORS)('team colour $name has AA contrast with white text', ({ hex }) => {
  expect(contrastRatio(hex, '#ffffff')).toBeGreaterThanOrEqual(4.5);
  expect(textOn(hex)).toBe('#ffffff');
});

test('textOn picks black for light backgrounds', () => {
  expect(textOn('#ffff00')).toBe('#000000');
});
