import { playPattern } from '../../audio/player.js';
import { createRecorder } from '../../audio/recorder.js';
import { api } from '../../lib/api.js';
import { uploadWithRetry } from '../../lib/uploadQueue.js';

export const SLACK_BEATS = 4;

function abortableDelay(ms, signal) {
  return new Promise((resolve) => {
    const id = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(id);
      resolve();
    });
  });
}

/** Seconds from the first recorded sample to the first count-in click. */
export function countinStartSeconds(playStartedAt, recordingStartTime) {
  return Math.round((playStartedAt - recordingStartTime) * 100000) / 100000;
}

/**
 * Run one team turn for a round created on the server:
 * (optional) reference playback -> count-in -> record -> upload -> score.
 * `emit(stage, data)` reports progress: reference, hit, countin, recording, level, uploading,
 * waiting, scored. Returns the API response { round, score }.
 */
export async function runTurn(
  round,
  { volume = 0.8, playReference = true, emit = () => {}, signal } = {},
) {
  const { pattern, bpm, length_beats: lengthBeats } = round.reference;
  const countIn = round.capture.count_in_beats;
  const spb = 60 / bpm;
  const aborted = () => signal?.aborted;

  if (playReference) {
    await api(`/api/rounds/${round.id}`, {
      method: 'PATCH',
      body: { status: 'playing_reference' },
    });
    emit('reference');
    await playPattern(pattern, bpm, {
      lengthBeats,
      volume,
      onItem: (item) => emit('hit', item),
    });
    if (aborted()) throw new DOMException('Stopped', 'AbortError');
  }

  const rec = await createRecorder({ onLevel: (rms) => emit('level', rms) });
  try {
    await api(`/api/rounds/${round.id}`, { method: 'PATCH', body: { status: 'recording' } });
    rec.start();
    let started = null;
    // Count-in clicks, then silence for the pattern length while the team plays.
    await playPattern(pattern, bpm, {
      countIn,
      lengthBeats,
      volume,
      playPattern: false,
      onStart: (s) => (started = s),
      onItem: (item) => emit(item.kind === 'count' ? 'countin' : 'hit', item),
    });
    if (aborted()) throw new DOMException('Stopped', 'AbortError');
    emit('recording');
    await abortableDelay(SLACK_BEATS * spb * 1000, signal);
    const take = await rec.stop();
    if (aborted()) throw new DOMException('Stopped', 'AbortError');

    emit('uploading');
    const form = new FormData();
    form.append('audio', take.wav, `round-${round.id}.wav`);
    form.append('countin_start_s', String(countinStartSeconds(started.startedAt, take.startTime)));
    const res = await uploadWithRetry(`/api/rounds/${round.id}/recording`, form, {
      onWaiting: (n) => emit('waiting', n),
    });
    emit('scored', res);
    return res;
  } finally {
    rec.close();
  }
}
