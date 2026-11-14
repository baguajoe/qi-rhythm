import { expect, test } from '@playwright/test';
import {
  TEAM_A,
  expectNoSeriousA11yIssues,
  login,
  micArgs,
  openDisplay,
  pickRhythmAndTeam,
  readState,
  resumeClass,
  runTurn,
} from './helpers.js';

test.use({ launchOptions: micArgs('silence.wav') });

const OVERRIDE_TOTAL = 50;

test('silence asks for review; override updates scoreboards; TV resyncs after a dropped connection', async ({
  page,
}) => {
  await login(page);
  await resumeClass(page);

  // TV with a controllable socket: we can drop and block it to simulate a Wi-Fi blip.
  let blocked = false;
  const live = [];
  const tv = await openDisplay(page, {
    beforeGoto: async (tvPage) => {
      await tvPage.routeWebSocket(/socket\.io/, (ws) => {
        if (blocked) return ws.close();
        const server = ws.connectToServer();
        live.push({ ws, server });
      });
      await tvPage.route(/socket\.io/, (route) => (blocked ? route.abort() : route.continue()));
    },
  });

  await pickRhythmAndTeam(page, TEAM_A);
  const total = await runTurn(page, TEAM_A);
  expect(total).toBeLessThan(10);
  await expect(page.getByText('Audio was unclear — confirm or adjust this score.')).toBeVisible();
  await expect(page.getByText('No drum hits were heard.')).toBeVisible();
  await expect(page.getByText(/Unclear recording/)).toBeVisible();
  await expect(tv.getByText(`${total} points`)).toBeVisible();

  const board = page.getByRole('table');
  const rowA = board.getByRole('row', { name: new RegExp(TEAM_A) });
  const before = Number(await rowA.getByRole('cell').first().textContent());
  expect(before).toBeGreaterThanOrEqual(readState().perfectTotal - 1);

  // Drop the TV's connection and keep it down.
  blocked = true;
  for (const { ws, server } of live) {
    await ws.close();
    await server.close();
  }
  await expect(tv.getByRole('status')).toHaveText(/Reconnecting/);

  // Instructor overrides the silent take while the TV is offline.
  await page.getByRole('button', { name: 'Adjust score' }).click();
  await page.getByLabel('Total (optional)').fill(String(OVERRIDE_TOTAL));
  await page.getByLabel('Reason (optional)').fill('Group played; mic was muted');
  await page.getByRole('button', { name: 'Save score' }).click();
  await expect(
    page.getByRole('heading', { name: `${TEAM_A}: ${OVERRIDE_TOTAL} points` }),
  ).toBeVisible();
  await expect(page.getByText(/computer total was 0/)).toBeVisible();
  const after = before + OVERRIDE_TOTAL;
  await expect(rowA.getByRole('cell').first()).toHaveText(
    new RegExp(`^(${after - 1}|${after}|${after + 1})$`),
  );

  // Restore the connection: the TV must resync to the new state within 5 seconds.
  const restoredAt = Date.now();
  blocked = false;
  await expect(tv.getByRole('status')).toHaveCount(0, { timeout: 5_000 });
  await expect(tv.getByText(`${OVERRIDE_TOTAL} points`)).toBeVisible({ timeout: 5_000 });
  await expect(tv.getByRole('listitem').filter({ hasText: TEAM_A })).toContainText(
    new RegExp(`(${after - 1}|${after}|${after + 1})$`),
    { timeout: 5_000 },
  );
  const resyncMs = Date.now() - restoredAt;
  test.info().annotations.push({ type: 'reconnect', description: `TV resynced in ${resyncMs} ms` });
  expect(resyncMs).toBeLessThan(5_000);

  await expectNoSeriousA11yIssues(tv, 'display view (after reconnect)');
});
