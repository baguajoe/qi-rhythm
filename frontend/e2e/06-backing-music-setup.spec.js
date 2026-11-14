import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import {
  CLAVE,
  TEAM_A,
  WAV_DIR,
  apiGet,
  expectNoSeriousA11yIssues,
  login,
  micArgs,
  pickRhythmAndTeam,
  readState,
  resumeClass,
  saveState,
} from './helpers.js';

// The "microphone" hears only the groove loop playing through the room speaker.
test.use({ launchOptions: micArgs('music-measure.wav') });

test('admin uploads loops, adds licenses, and measures the music level', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));
  await login(page);

  // ---- Backing music page (admin only)
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Backing music' })
    .click();
  await expect(page.getByRole('heading', { name: 'Backing music', level: 1 })).toBeVisible();
  const { id: clave } = (await apiGet(page, '/api/rhythms')).rhythms.find((r) => r.title === CLAVE);
  await page.getByLabel('Rhythm').selectOption(String(clave));
  await expect(page.getByText(/No loops yet/)).toBeVisible();

  // Full version, licensed in the upload form.
  await page.getByLabel('WAV file').setInputFiles(resolve(WAV_DIR, 'groove-full.wav'));
  await page.getByRole('radio', { name: /^Full/ }).check();
  await page.getByLabel('Where is this track from?').selectOption('original');
  await page.getByLabel(/License notes/).fill('Recorded by the project owner in Cubase, 2026.');
  await page.getByRole('button', { name: 'Upload loop' }).click();
  await expect(page.getByText('Uploaded the full loop.')).toBeVisible();
  const full = page.getByRole('article', { name: /^Full/ });
  await expect(full.getByText('Ready for classes')).toBeVisible();
  await expect(full.getByText('✓ matches')).toBeVisible();

  // Groove only, 1 bar, uploaded without a license: not usable until the notes are added.
  await page.getByLabel('WAV file').setInputFiles(resolve(WAV_DIR, 'groove-bed.wav'));
  await page.getByRole('radio', { name: /Groove only/ }).check();
  await page.getByRole('spinbutton', { name: 'Bars' }).last().fill('1');
  await page.getByRole('button', { name: 'Upload loop' }).click();
  const bed = page.getByRole('article', { name: /Groove only/ });
  await expect(bed.getByText('Not ready yet')).toBeVisible();
  await expect(bed.getByText(/Add the source and license notes/)).toBeVisible();
  await expect(bed.getByText('✓ matches')).toBeVisible();
  await bed.getByLabel('Where is this track from?').selectOption('commissioned');
  await bed.getByLabel(/License notes/).fill('Commissioned groove, live class use allowed.');
  await bed.getByRole('button', { name: 'Save changes' }).click();
  await expect(bed.getByText('Ready for classes')).toBeVisible();
  await expectNoSeriousA11yIssues(page, 'backing music page');

  // The loop plays in the browser (decoded through the API with the instructor's token).
  await bed.getByRole('button', { name: /Listen to this loop/ }).click();
  await expect(bed.getByLabel('Groove only loop')).toBeVisible();

  // ---- Class page: measure the music level before the first musical turn.
  await resumeClass(page);
  await pickRhythmAndTeam(page, TEAM_A);
  const panel = page.getByRole('region', { name: 'Backing music' });
  await expect(panel.getByText(/Full version while listening, groove only/)).toBeVisible();
  await expect(panel.getByText(/Measure the music level once/)).toBeVisible();
  await panel.getByRole('button', { name: /Measure music level/ }).click();
  await expect(page.getByText(/Measuring the music level/)).toBeVisible();
  await expect(page.getByText(/Music level measured\. The app now knows/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(panel.getByText(/Music level measured \w/)).toBeVisible();

  const tracks = (await apiGet(page, `/api/backing-tracks?rhythm_id=${clave}`)).tracks;
  const groove = tracks.find((t) => t.version === 'bed');
  test.info().annotations.push({
    type: 'music level',
    description: JSON.stringify(groove.music_level),
  });
  expect(groove.music_level.transients_per_loop).toBe(8);

  // Listening uses the full loop (synthesized pattern muted) and finishes normally.
  // (Earlier specs left a score on screen, so the button already reads "Play again".)
  const play = page.getByRole('button', { name: /Play the pattern|Play again/ });
  await play.click();
  await expect(page.getByText('Playing the pattern…')).toBeVisible();
  await expect(play).toBeDisabled();
  await expect(play).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByText('Ready when you are.')).toBeVisible();

  expect(pageErrors).toEqual([]);
  saveState({ claveId: clave, grooveId: groove.id, sessionIdForMusic: readState().sessionId });
});
