import { useCallback, useEffect, useRef, useState } from 'react';
import { getToken } from '../../lib/api.js';
import { connectSession } from '../../lib/socket.js';

/** Instructor socket: sends live control events so the Display View can follow along. */
export function useSessionSocket(sessionId) {
  const socketRef = useRef(null);
  const lastLevel = useRef(0);
  const [status, setStatus] = useState('connecting');

  useEffect(() => {
    if (!sessionId) return undefined;
    const socket = connectSession({ token: getToken(), sessionId, onStatus: setStatus });
    socketRef.current = socket;
    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [sessionId]);

  const send = useCallback((event, payload = {}) => {
    if (event === 'control:level') {
      const now = performance.now();
      if (now - lastLevel.current < 100) return; // throttle to ~10 updates/second
      lastLevel.current = now;
    }
    socketRef.current?.emit(event, payload);
  }, []);

  return { send, status };
}
