import { ApiError } from './api.js';
import { uploadWithRetry } from './uploadQueue.js';

test('retries network failures then succeeds', async () => {
  let n = 0;
  global.fetch = vi.fn(async () => {
    n += 1;
    if (n < 3) throw new TypeError('network down');
    return { ok: true, status: 201, json: async () => ({ ok: 1 }) };
  });
  const waiting = vi.fn();
  const res = await uploadWithRetry('/api/rounds/1/recording', new FormData(), {
    onWaiting: waiting,
    sleep: async () => {},
  });
  expect(res).toEqual({ ok: 1 });
  expect(waiting).toHaveBeenCalledTimes(2);
});

test('does not retry server-side errors', async () => {
  global.fetch = vi.fn(async () => ({
    ok: false,
    status: 422,
    json: async () => ({ error: 'Unreadable' }),
  }));
  await expect(uploadWithRetry('/x', new FormData(), { sleep: async () => {} })).rejects.toThrow(
    'Unreadable',
  );
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('gives up after the retry limit', async () => {
  global.fetch = vi.fn(async () => {
    throw new TypeError('offline');
  });
  await expect(
    uploadWithRetry('/x', new FormData(), { retries: 2, sleep: async () => {} }),
  ).rejects.toBeInstanceOf(ApiError);
  expect(global.fetch).toHaveBeenCalledTimes(3);
});
