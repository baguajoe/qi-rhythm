import { io } from 'socket.io-client';
import { API_URL } from './api.js';

/**
 * Connect to the session room. Re-joins automatically after every (re)connect, and the server
 * replies with a full `session:state` snapshot so the client resyncs. Reconnect delays are kept
 * short so the Display recovers within a few seconds.
 */
export function connectSession({ token, sessionId, onEvent, onStatus }) {
  const socket = io(API_URL, {
    auth: { token },
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 500,
    reconnectionDelayMax: 2000,
    randomizationFactor: 0.2,
    timeout: 4000,
  });
  socket.on('connect', () => {
    onStatus?.('connected');
    socket.emit('join_session', { session_id: sessionId }, (ack) => {
      if (ack && ack.ok === false) onStatus?.('denied');
    });
  });
  socket.on('disconnect', () => onStatus?.('reconnecting'));
  socket.on('connect_error', (err) => onStatus?.(socket.active ? 'reconnecting' : 'denied', err));
  socket.onAny((event, payload) => onEvent?.(event, payload));
  return socket;
}
