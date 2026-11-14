import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { contrastRatio } from '../lib/contrast.js';

const css = readFileSync(resolve(__dirname, '../styles/global.css'), 'utf8');

function tokens(selector) {
  const start = css.indexOf(selector);
  const block = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start));
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]),
  );
}

const normal = tokens(':root {');
const high = { ...normal, ...tokens(":root[data-contrast='high']") };

describe.each([
  ['normal (WCAG AA)', normal, 4.5],
  ['high contrast (WCAG AAA)', high, 7],
])('%s palette', (_name, t, textMin) => {
  test.each([
    ['text on background', 'text', 'bg'],
    ['text on surface', 'text', 'surface'],
    ['muted text on background', 'muted', 'bg'],
    ['muted text on surface', 'muted', 'surface'],
    ['button text on primary', 'primary-text', 'primary'],
    ['primary (secondary buttons, links) on surface', 'primary', 'surface'],
    ['success text on surface', 'success', 'surface'],
  ])('%s', (_label, fg, bg) => {
    expect(contrastRatio(t[fg], t[bg])).toBeGreaterThanOrEqual(textMin);
  });

  test.each([
    ['focus ring on background', 'focus', 'bg'],
    ['borders on surface', 'border', 'surface'],
    ['accent (current beat, extra hits) on surface', 'accent', 'surface'],
  ])('non-text %s >= 3:1', (_label, fg, bg) => {
    expect(contrastRatio(t[fg], t[bg])).toBeGreaterThanOrEqual(3);
  });
});

test('current beat (accent) is distinguishable from played beats (primary)', () => {
  for (const t of [normal, high])
    expect(contrastRatio(t.accent, t.primary)).toBeGreaterThanOrEqual(1.4);
});

test('touch targets and base font size', () => {
  expect(css).toMatch(/--tap:\s*56px/);
  expect(css).toMatch(/font-size:\s*20px/);
});

test('reduced motion is respected', () => {
  expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
});

test('display view headlines are at least 48px', () => {
  const display = readFileSync(
    resolve(__dirname, '../features/display/DisplayPage.module.css'),
    'utf8',
  );
  const mins = [...display.matchAll(/clamp\((\d+)px/g)].map((m) => Number(m[1]));
  expect(mins.length).toBeGreaterThan(4);
  expect(Math.min(...mins)).toBeGreaterThanOrEqual(48);
});
