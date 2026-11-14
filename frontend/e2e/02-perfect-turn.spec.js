import { expect, test } from '@playwright/test';
import {
  CLAVE,
  PERFECT_MIN,
  TEAM_A,
  expectNoSeriousA11yIssues,
  latestRound,
  login,
  micArgs,
  openDisplay,
  pickRhythmAndTeam,
  readTurnCues,
  runTurn,
  saveState,
  watchTurnCues,
} from './helpers.js';

test.use({ launchOptions: micArgs('perfect.wav') });

test('perfect take scores high and the TV follows live', async ({ page }) => {
  await login(page);
  await expect(page.getByText(/microphone records the room/)).toBeVisible();
  await expect(page.getByLabel('Room setup to use')).toHaveValue(/\d+/);
  await page.getByRole('button', { name: /Start class session/ }).click();
  await expect(page.getByRole('heading', { name: 'Class in progress' })).toBeVisible();
  const sessionId = await page.evaluate(() => Number(localStorage.getItem('qi.activeSession')));
  saveState({ sessionId });

  const tv = await openDisplay(page);
  await pickRhythmAndTeam(page, TEAM_A);
  await expect(tv.getByRole('heading', { level: 1 })).toContainText(TEAM_A);
  await expect(tv.getByText(`Rhythm: ${CLAVE}`)).toBeVisible();

  // Play the pattern (preview): the TV shows the listening screen with the beat visualizer.
  await page.getByRole('button', { name: /Play the pattern/ }).click();
  await expect(tv.getByText('Listen to the pattern')).toBeVisible();
  await expect(page.getByRole('button', { name: /Play again/ })).toBeEnabled({ timeout: 20_000 });

  // Team turn. Watch the TV for each live stage while the turn runs.
  const tvStages = Promise.all([
    expect(tv.getByText('PLAY!')).toBeVisible({ timeout: 40_000 }),
    expect(tv.getByText('Your turn!')).toBeVisible({ timeout: 40_000 }),
    expect(tv.getByRole('meter', { name: 'Drum sound' })).toBeVisible({ timeout: 40_000 }),
  ]);
  await watchTurnCues(page);
  const total = await runTurn(page, TEAM_A);
  await tvStages;

  // "Your turn!" must appear exactly when the team starts: the beat after the final count "1"
  // (one beat = 667 ms at 90 BPM), not after the pattern has already played out.
  const cues = await readTurnCues(page);
  const gapMs = cues.yourTurn - cues.finalCount;
  test.info().annotations.push({
    type: 'your turn',
    description: `"1" -> "Your turn!" ${Math.round(gapMs)} ms`,
  });
  expect(gapMs).toBeGreaterThan(667 - 120);
  expect(gapMs).toBeLessThan(667 + 120);

  const round = await latestRound(page);
  test.info().annotations.push({
    type: 'score',
    description: `perfect total=${total} offset=${round.score.alignment.global_offset_ms}ms matched=${round.score.alignment.matched.length}/${round.score.alignment.expected.length} confidence=${round.score.confidence}`,
  });
  expect(total).toBeGreaterThanOrEqual(PERFECT_MIN);
  expect(round.score.needs_review).toBe(false);
  await expect(page.getByText(/Clear recording/)).toBeVisible();

  // TV shows the result in real time
  await expect(tv.getByText(`${total} points`)).toBeVisible();
  await expect(tv.getByRole('img', { name: /out of 5 stars/ })).toBeVisible();

  await page.getByRole('button', { name: /Confirm score/ }).click();
  await expect(page.getByText('✓ Score confirmed')).toBeVisible();

  await expectNoSeriousA11yIssues(page, 'dashboard');
  await expectNoSeriousA11yIssues(tv, 'display view (results)');
  saveState({ perfectTotal: total });
});
