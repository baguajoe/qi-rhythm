import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

// Per-device display preferences (not personal data).
const KEY = 'qi.settings';
export const DEFAULT_SETTINGS = {
  highContrast: false,
  spokenInstructions: false,
  speechRate: 0.9,
  cooperativeMode: false,
};

const SettingsContext = createContext(null);

function load() {
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
    } catch {
      /* ignore */
    }
    document.documentElement.dataset.contrast = settings.highContrast ? 'high' : 'normal';
  }, [settings]);

  const update = useCallback((patch) => setSettings((s) => ({ ...s, ...patch })), []);
  const value = useMemo(() => ({ settings, update }), [settings, update]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used inside SettingsProvider');
  return ctx;
}
