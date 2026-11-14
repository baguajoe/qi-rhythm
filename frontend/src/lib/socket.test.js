import { SOCKET_OPTIONS, connectSession } from './socket.js';

const fake = {
  handlers: {},
  connected: false,
  connect: vi.fn(),
  disconnect: vi.fn(),
  emit: vi.fn(),
  onAny: vi.fn(),
};
fake.on = (ev, fn) => (fake.handlers[ev] = fn);
vi.mock('socket.io-client', () => ({ io: vi.fn(() => fake) }));

test('worst-case recovery after the network returns stays well under 5 seconds', () => {
  const worst =
    SOCKET_OPTIONS.timeout +
    SOCKET_OPTIONS.reconnectionDelayMax * (1 + SOCKET_OPTIONS.randomizationFactor);
  expect(worst).toBeLessThan(3500);
});

test('re-joins the session on every connect and retries when the browser comes back online', () => {
  const status = [];
  const socket = connectSession({ token: 't', sessionId: 9, onStatus: (s) => status.push(s) });
  fake.handlers.connect();
  expect(fake.emit).toHaveBeenCalledWith('join_session', { session_id: 9 }, expect.any(Function));
  fake.handlers.disconnect();
  expect(status).toEqual(['connected', 'reconnecting']);

  window.dispatchEvent(new Event('online'));
  expect(fake.connect).toHaveBeenCalledTimes(1);
  window.dispatchEvent(new Event('online'));
  expect(fake.connect).toHaveBeenCalledTimes(2); // listener survives retries

  socket.disconnect();
  window.dispatchEvent(new Event('online'));
  expect(fake.connect).toHaveBeenCalledTimes(2); // removed on real disconnect
});
