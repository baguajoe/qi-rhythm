import { expect, test } from '@playwright/test';
import { API } from './helpers.js';

// Drop and restore the TV's live connection six times with outages of different lengths. Each
// time it must be back in sync (no "Reconnecting…" banner) within 5 seconds of the network
// returning. Independent of the other specs: it sets up its own organization via the API.
test('TV recovers from repeated dropped connections within 5 seconds', async ({
  page,
  request,
}) => {
  const reg = await (
    await request.post(`${API}/api/auth/register`, {
      data: {
        organization_name: 'Reconnect Test',
        display_name: 'R',
        email: `reconnect-${Date.now()}@example.com`,
        password: 'reconnect-pass-1',
      },
    })
  ).json();
  const headers = { Authorization: `Bearer ${reg.access_token}` };
  const sess = await (await request.post(`${API}/api/sessions`, { headers, data: {} })).json();
  const code = await (
    await request.post(`${API}/api/sessions/${sess.session.id}/display-code`, { headers })
  ).json();

  let blocked = false;
  const live = [];
  await page.routeWebSocket(/socket\.io/, (ws) => {
    if (blocked) return ws.close();
    live.push({ ws, server: ws.connectToServer() });
  });
  await page.route(/socket\.io/, (route) => (blocked ? route.abort() : route.continue()));
  await page.goto(`/display/${sess.session.id}?code=${code.code}`);
  await expect(page.getByRole('status')).toHaveCount(0);

  const timings = [];
  for (let i = 0; i < 6; i += 1) {
    blocked = true;
    for (const { ws, server } of live.splice(0)) {
      await ws.close();
      await server.close();
    }
    await expect(page.getByRole('status')).toHaveText(/Reconnecting/);
    await page.waitForTimeout(2500 + i * 700);
    const restoredAt = Date.now();
    blocked = false;
    await expect(page.getByRole('status')).toHaveCount(0, { timeout: 10_000 });
    timings.push(Date.now() - restoredAt);
  }
  test
    .info()
    .annotations.push({ type: 'reconnect', description: `resync ms: ${timings.join(', ')}` });
  expect(Math.max(...timings)).toBeLessThan(5_000);
});
