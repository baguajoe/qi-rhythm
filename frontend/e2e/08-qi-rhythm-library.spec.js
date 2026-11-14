import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import { API, WAV_DIR, login, readState, resumeClass } from './helpers.js';

const OTHER_RHYTHM = 'Son Clave 2-3'; // untouched by the earlier specs
const DATABASE_URL =
  process.env.E2E_DATABASE_URL || 'postgresql+psycopg://qi:qi@localhost:5432/qi_rhythm_e2e';

/** Super-admin is granted only on the server command line, exactly as in production. */
function grantSuperadmin(email) {
  execFileSync(
    process.env.E2E_PYTHON || '.venv/bin/python',
    ['-m', 'flask', '--app', 'wsgi', 'set-role', email, 'superadmin'],
    { cwd: resolve(import.meta.dirname, '../../backend'), env: { ...process.env, DATABASE_URL } },
  );
}

test('the Qi Rhythm team publishes a library loop that every organization gets', async ({
  page,
  browser,
  request,
}) => {
  // ---- Eye Forge Studios account (own organization), promoted to super-admin.
  const email = `team-${Date.now()}@eyeforge.example`;
  const password = 'library-pass-123';
  const reg = await request.post(`${API}/api/auth/register`, {
    data: {
      organization_name: 'Eye Forge Studios',
      display_name: 'Qi Rhythm team',
      email,
      password,
    },
  });
  expect(reg.ok()).toBeTruthy();
  grantSuperadmin(email);

  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Backing music' })
    .click();
  const rhythms = (
    await (
      await request.get(`${API}/api/rhythms`, {
        headers: { Authorization: `Bearer ${(await reg.json()).access_token}` },
      })
    ).json()
  ).rhythms;
  const rhythm = rhythms.find((r) => r.title === OTHER_RHYTHM);
  await page.getByLabel('Rhythm').selectOption(String(rhythm.id));

  await page
    .getByRole('group', { name: 'Add to' })
    .getByLabel(/Qi Rhythm Library/)
    .check();
  await page.getByLabel('WAV file').setInputFiles(resolve(WAV_DIR, 'groove-bed.wav'));
  await page.getByRole('radio', { name: /Groove only/ }).check();
  await page.getByRole('spinbutton', { name: 'Bars' }).last().fill('1');
  const upload = page.locator('form');
  await upload.getByLabel('Where is this track from?').selectOption('original');
  await upload.getByLabel(/License notes/).fill('Qi Rhythm Original by Eye Forge Studios, 2026.');
  await page.getByRole('button', { name: 'Upload loop' }).click();
  await expect(
    page.getByText('Uploaded the groove only loop to the Qi Rhythm Library.'),
  ).toBeVisible();
  const library = page.getByRole('region', { name: 'Qi Rhythm Library' });
  await expect(library.getByText('★ Qi Rhythm Original')).toBeVisible();
  await expect(library.getByRole('button', { name: 'Save changes' })).toBeVisible();

  // ---- An ordinary organization admin (from spec 01) gets it automatically, read-only.
  const ctx = await browser.newContext();
  const coach = await ctx.newPage();
  await login(coach);
  const token = await coach.evaluate(() => localStorage.getItem('qi.token'));
  const denied = await coach.request.post(`${API}/api/rhythms/${rhythm.id}/backing-tracks`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      scope: 'library',
      version: 'bed',
      bpm: '90',
      bars: '1',
      audio: { name: 'x.wav', mimeType: 'audio/wav', buffer: Buffer.from('RIFF') },
    },
  });
  expect(denied.status()).toBe(403);

  await coach.goto('/music');
  await coach.getByLabel('Rhythm').selectOption(String(rhythm.id));
  const seen = coach.getByRole('region', { name: 'Qi Rhythm Library' });
  await expect(seen.getByText('★ Qi Rhythm Original')).toBeVisible();
  await expect(seen.getByText('Plays in your classes')).toBeVisible();
  await expect(seen.getByRole('button', { name: 'Save changes' })).toHaveCount(0);

  expect(readState().sessionId).toBeTruthy();
  await resumeClass(coach);
  await coach.getByRole('button', { name: new RegExp(OTHER_RHYTHM) }).click();
  const panel = coach.getByRole('region', { name: 'Backing music' });
  await expect(panel.getByText('★ Qi Rhythm Original')).toBeVisible();
  await expect(panel.getByText(/From the Qi Rhythm Library/)).toBeVisible();
  await ctx.close();
});
