import { io } from 'socket.io-client';
import { API_URL } from './api.js';

/**
 * Connect to the session room. Re-joins automatically after every (re)connect, and the server
 * replies with a full `session:state` snapshot so the client resyncs.
 *
 * Recovery budget (target: back in sync < 5 s after the network returns): an attempt made while
 * the network was down can hang until `timeout`, then waits up to `reconnectionDelayMax` (+20%)
 * before retrying, so worst case is about 2 s + 1.2 s. The browser's `online` event also triggers
 * an immediate retry.
 */
export const SOCKET_OPTIONS = {
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionDelay: 300,
  reconnectionDelayMax: 1000,
  randomizationFactor: 0.2,
  timeout: 2000,
};

export function connectSession({ token, sessionId, onEvent, onStatus }) {
  const socket = io(API_URL, { ...SOCKET_OPTIONS, auth: { token } });
  const rawDisconnect = socket.disconnect.bind(socket);
  const retryNow = () => {
    if (!socket.connected) {
      rawDisconnect();
      socket.connect();
    }
  };
  window.addEventListener('online', retryNow);
  socket.disconnect = () => {
    window.removeEventListener('online', retryNow);
    return rawDisconnect();
  };
  socket.on('connect', () => {
    onStatus?.('connected');
    socket.emit('join_session', { session_id: sessionId }, (ack) => {
      if (ack && ack.ok === false) {
        console.warn('Qi Rhythm: could not join the class session:', ack.error);
        onStatus?.('denied');
      }
    });
  });
  socket.on('disconnect', () => onStatus?.('reconnecting'));
  socket.on('connect_error', (err) => {
    console.warn('Qi Rhythm: live connection problem:', err?.message);
    onStatus?.(socket.active ? 'reconnecting' : 'denied', err);
  });
  socket.onAny((event, payload) => onEvent?.(event, payload));
  return socket;
}
