import { useCallback, useEffect, useRef, useState } from 'react';
import { playPattern, stopPlayback } from './player.js';

/** React wrapper around the Tone.js player, tracking which hit is sounding now. */
export function usePatternPlayer() {
  const [state, setState] = useState({ playing: false, playedThrough: -1, count: null });
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stopPlayback();
    };
  }, []);

  const play = useCallback(async (pattern, bpm, opts = {}) => {
    setState({ playing: true, playedThrough: -1, count: null });
    const result = await playPattern(pattern, bpm, {
      ...opts,
      onItem: (item) => {
        if (!mounted.current) return;
        if (item.kind === 'count') setState((s) => ({ ...s, count: item.countNumber }));
        else setState((s) => ({ ...s, count: null, playedThrough: item.index }));
        opts.onItem?.(item);
      },
    });
    if (mounted.current)
      setState((s) => ({
        ...s,
        playing: false,
        count: null,
        playedThrough: Number.MAX_SAFE_INTEGER,
      }));
    return result;
  }, []);

  const stop = useCallback(() => {
    stopPlayback();
    setState({ playing: false, playedThrough: -1, count: null });
  }, []);

  return { ...state, play, stop };
}
