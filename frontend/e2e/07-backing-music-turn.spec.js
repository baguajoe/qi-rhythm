import { expect, test } from '@playwright/test';
import {
  PERFECT_MIN,
  TEAM_A,
  latestRound,
  login,
  micArgs,
  pickRhythmAndTeam,
  readState,
  resumeClass,
} from './helpers.js';

// The "microphone" hears the team playing the clave with the groove loop underneath.
test.use({ launchOptions: micArgs('music-turn.wav') });

test('a team turn over the groove scores like a quiet room', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));
  await login(page);
  await resumeClass(page);
  await pickRhythmAndTeam(page, TEAM_A);
  await expect(page.getByText(/Full version while listening, groove only/)).toBeVisible();

  const heading = page.getByRole('heading', { name: new RegExp(`^${TEAM_A}: \\d+ points$`) });
  await page.getByRole('button', { name: /Start team turn/ }).click();
  await expect(heading).toBeHidden(); // the earlier spec's score clears when the turn starts
  await expect(page.getByText('Listen to the pattern…')).toBeVisible();
  await expect(heading).toBeVisible({ timeout: 90_000 });
  const total = Number((await heading.textContent()).match(/(\d+) points/)[1]);

  const round = await latestRound(page);
  test.info().annotations.push({
    type: 'score',
    description: `music total=${total} matched=${round.score.alignment.matched.length}/${round.score.alignment.expected.length} extras=${round.score.alignment.extras.length} confidence=${round.score.confidence}`,
  });
  expect(round.backing_track_id).toBe(readState().grooveId);
  expect(round.music_volume_used).toBe(0.6);
  expect(round.score.alignment.extras).toHaveLength(0); // the groove's drums weren't counted
  expect(total).toBeGreaterThanOrEqual(PERFECT_MIN);
  expect(round.score.needs_review).toBe(false);
  expect(pageErrors).toEqual([]);
});
