import { ApiError, api } from './api.js';

// Retries recording uploads through short network blips (status 0 = unreachable). The take stays
// in memory until it is sent, and the UI shows "waiting for connection" meanwhile.
// TODO(phase-3): persist pending takes in IndexedDB so they survive a page reload.
export async function uploadWithRetry(
  path,
  form,
  { retries = 6, baseDelayMs = 1000, onWaiting, sleep } = {},
) {
  const wait = sleep || ((ms) => new Promise((r) => setTimeout(r, ms)));
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await api(path, { method: 'POST', body: form });
    } catch (err) {
      if (!(err instanceof ApiError) || err.status !== 0 || attempt >= retries) throw err;
      onWaiting?.(attempt + 1);
      await wait(Math.min(15000, baseDelayMs * 2 ** attempt));
    }
  }
}
