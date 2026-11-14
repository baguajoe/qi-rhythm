import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { expect } from '@playwright/test';

const require = createRequire(import.meta.url);
export const WAV_DIR = resolve(import.meta.dirname, '.wavs');
export const STATE_FILE = resolve(import.meta.dirname, '.state.json');
export const API = `http://localhost:${process.env.E2E_API_PORT || 5001}`;

// Fixed values from the WAV generator / seed library.
export const CLAVE = 'Son Clave 3-2';
export const TEAM_A = 'Sunflowers';
export const TEAM_B = 'Blue Jays';
export const INSTRUCTOR = {
  name: 'Coach E2E',
  org: 'E2E Community Center',
  email: 'coach.e2e@example.com',
  password: 'drum-circle-e2e',
};

// Score expectations: same >= 95 bar as the product criterion. Browser timing offsets observed in
// Codespaces were 40-90 ms and are absorbed by the engine's offset correction, so no widening was
// needed. E2E_PERFECT_MIN can lower it on an unusually slow CI runner (see CLAUDE.md).
export const PERFECT_MIN = Number(process.env.E2E_PERFECT_MIN || 95);
export const MISSED_GAP_MIN = 10;

/** Chromium flags that make the fake microphone play a WAV file once per mic open. */
export function micArgs(wav) {
  return {
    args: [
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${resolve(WAV_DIR, wav)}%noloop`,
      '--autoplay-policy=no-user-gesture-required',
    ],
  };
}

export function readState() {
  return existsSync(STATE_FILE) ? JSON.parse(readFileSync(STATE_FILE, 'utf8')) : {};
}

export function saveState(patch) {
  writeFileSync(STATE_FILE, JSON.stringify({ ...readState(), ...patch }, null, 2));
}

export async function login(page) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(INSTRUCTOR.email);
  await page.getByLabel('Password').fill(INSTRUCTOR.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
}

/** Re-open the class session started by an earlier spec (a fresh browser has empty storage). */
export async function resumeClass(page) {
  const { sessionId } = readState();
  await page.evaluate((id) => localStorage.setItem('qi.activeSession', String(id)), sessionId);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Class in progress' })).toBeVisible();
}

export async function apiGet(page, path) {
  const token = await page.evaluate(() => localStorage.getItem('qi.token'));
  const res = await page.request.get(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Latest round of the session, straight from the API (for diagnostics and exact values). */
export async function latestRound(page) {
  const { sessionId } = readState();
  const data = await apiGet(page, `/api/sessions/${sessionId}`);
  return data.rounds.at(-1);
}

export async function pickRhythmAndTeam(page, team) {
  await page.getByRole('button', { name: new RegExp(CLAVE) }).click();
  await page
    .getByRole('group', { name: '2. Whose turn?' })
    .getByRole('button', { name: new RegExp(team) })
    .click();
}

/** Run a team turn from the dashboard and return the total shown in the score heading. */
export async function runTurn(page, team) {
  await page.getByRole('button', { name: /Start team turn/ }).click();
  const heading = page.getByRole('heading', { name: new RegExp(`^${team}: \\d+ points$`) });
  await expect(heading).toBeVisible({ timeout: 90_000 });
  return Number((await heading.textContent()).match(/(\d+) points/)[1]);
}

/** Open the TV Display View in a second page using the dashboard's TV code. */
export async function openDisplay(page, { beforeGoto } = {}) {
  await page.getByRole('button', { name: 'Get a TV code' }).click();
  const code = (await page.locator('p[aria-label^="TV code"]').textContent()).trim();
  const { sessionId } = readState();
  const tv = await page.context().newPage();
  if (beforeGoto) await beforeGoto(tv);
  await tv.goto(`/display/${sessionId}?code=${code}`);
  await expect(tv.getByRole('status')).toHaveCount(0, { timeout: 10_000 }); // connected (no banner)
  return tv;
}

/** axe-core in the real browser (incl. colour contrast). Fails on serious/critical issues. */
export async function expectNoSeriousA11yIssues(page, label) {
  await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
  const violations = await page.evaluate(async () => {
    const r = await window.axe.run(document, {
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'],
      },
    });
    return r.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
    }));
  });
  const serious = violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(serious, `${label}: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
  return violations;
}
