import { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api.js';

const KEY = 'qi.activeSession';

function storedId() {
  try {
    return Number(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

/** The instructor's active class session, kept in sync with the server. */
export function useClassSession() {
  const [sessionId, setSessionId] = useState(storedId);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const remember = (id) => {
    try {
      if (id) localStorage.setItem(KEY, String(id));
      else localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
    setSessionId(id);
  };

  const refresh = useCallback(async () => {
    if (!sessionId) return null;
    try {
      const d = await api(`/api/sessions/${sessionId}`);
      if (d.session.ended_at) {
        remember(null);
        setData(null);
        return null;
      }
      setData(d);
      return d;
    } catch (e) {
      if (e.status === 404) remember(null);
      setError(e.message);
      return null;
    }
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const start = useCallback(async (body) => {
    const d = await api('/api/sessions', { method: 'POST', body });
    remember(d.session.id);
    setData(d);
    return d;
  }, []);

  const end = useCallback(async () => {
    if (!sessionId) return;
    await api(`/api/sessions/${sessionId}/end`, { method: 'POST' });
    remember(null);
    setData(null);
  }, [sessionId]);

  const updateSettings = useCallback(
    async (patch) => {
      setData(
        (d) =>
          d && { ...d, session: { ...d.session, settings: { ...d.session.settings, ...patch } } },
      );
      try {
        const d = await api(`/api/sessions/${sessionId}`, {
          method: 'PATCH',
          body: { settings: patch },
        });
        setData(d);
      } catch (e) {
        setError(e.message);
        refresh();
      }
    },
    [sessionId, refresh],
  );

  return { sessionId, data, error, setError, refresh, start, end, updateSettings, setData };
}
