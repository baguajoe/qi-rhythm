import { expect, test } from '@playwright/test';
import {
  INSTRUCTOR,
  TEAM_A,
  TEAM_B,
  expectNoSeriousA11yIssues,
  micArgs,
  saveState,
} from './helpers.js';

test.use({ launchOptions: micArgs('calibration.wav') });

test('instructor registers, runs room setup, and makes two teams', async ({ page }) => {
  // Register
  await page.goto('/login');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByLabel('Your name').fill(INSTRUCTOR.name);
  await page.getByLabel('Organization name').fill(INSTRUCTOR.org);
  await page.getByLabel('Email').fill(INSTRUCTOR.email);
  await page.getByLabel('Password').fill(INSTRUCTOR.password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Class', exact: true })).toBeVisible();

  // Sign out and back in
  await page.getByRole('button', { name: /Sign out/ }).click();
  await page.getByLabel('Email').fill(INSTRUCTOR.email);
  await page.getByLabel('Password').fill(INSTRUCTOR.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();

  // Room setup (calibration wizard). The fake mic replays calibration.wav for each step.
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Room setup' })
    .click();
  await page.getByRole('button', { name: 'Start room setup' }).click();
  const results = {};
  for (const [step, expected] of [
    ['noise', /quiet|a little noisy/],
    ['latency', /Got it/],
    ['sensitivity', /Sounds good/],
  ]) {
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    const notice = page.getByRole('status').filter({ hasText: expected });
    await expect(notice).toBeVisible({ timeout: 30_000 });
    results[step] = await notice.textContent();
    await page.getByRole('button', { name: 'Next' }).click();
  }
  const latencyText = await page.locator('dt:has-text("Timing adjustment") + dd').textContent();
  test.info().annotations.push({
    type: 'calibration',
    description: `${JSON.stringify(results)} latency=${latencyText}`,
  });
  await page.getByLabel('Name for this room or laptop').fill('E2E room');
  await page.getByRole('button', { name: 'Save setup' }).click();
  await expect(page.getByRole('heading', { name: 'All set!' })).toBeVisible();
  await expect(page.getByText(/E2E room: timing adjustment/)).toBeVisible();

  // Two teams
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Teams' }).click();
  const form = page.getByRole('form', { name: 'Make a new team' });
  for (const name of [TEAM_A, TEAM_B]) {
    await form.getByLabel('Team name').fill(name);
    await form.getByRole('button', { name: 'Add team' }).click();
    await expect(page.getByRole('heading', { name: new RegExp(name) })).toBeVisible();
  }
  await expectNoSeriousA11yIssues(page, 'teams page');
  saveState({ latency: latencyText });
});
