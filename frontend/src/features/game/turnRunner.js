import { chooseMusic, loadTrack, measureLoops } from '../../audio/music.js';
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

/** Load the backing track for a phase; any failure falls back to the synthesized sounds. */
export async function prepareMusic(music, phase, { musicOn = true, volume = 0.6, onError } = {}) {
  const pick = chooseMusic(music, phase, musicOn && volume > 0);
  if (!pick) return null;
  try {
    const buffer = await loadTrack(pick.track);
    return { ...pick, buffer, volume };
  } catch (e) {
    onError?.(e);
    return null;
  }
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
  {
    volume = 0.8,
    musicVolume = 0.6,
    musicOn = true,
    playReference = true,
    emit = () => {},
    signal,
  } = {},
) {
  const { pattern, bpm, length_beats: lengthBeats, music } = round.reference;
  const musicOpts = { musicOn, volume: musicVolume, onError: () => emit('music-error') };
  const countIn = round.capture.count_in_beats;
  const spb = 60 / bpm;
  const aborted = () => signal?.aborted;
  // Decode the music before anything starts (cached after the first time).
  const [listen, bed] = await Promise.all([
    playReference ? prepareMusic(music, 'listen', musicOpts) : null,
    prepareMusic(music, 'turn', musicOpts),
  ]);

  if (playReference) {
    await api(`/api/rounds/${round.id}`, {
      method: 'PATCH',
      body: { status: 'playing_reference' },
    });
    emit('reference');
    await playPattern(pattern, bpm, {
      lengthBeats,
      volume,
      muteHits: listen?.muteHits,
      music: listen,
      onItem: (item) => emit('hit', item),
    });
    if (aborted()) throw new DOMException('Stopped', 'AbortError');
  }

  const rec = await createRecorder({ onLevel: (rms) => emit('level', rms) });
  let bedHandle = null;
  try {
    await api(`/api/rounds/${round.id}`, { method: 'PATCH', body: { status: 'recording' } });
    rec.start();
    let started = null;
    // Count-in clicks, then the team plays (over the groove-only track, if there is one, which
    // starts with the first click and keeps going through the slack bar).
    const played = await playPattern(pattern, bpm, {
      countIn,
      lengthBeats,
      volume,
      playPattern: false,
      music: bed,
      keepMusic: true,
      onStart: (s) => (started = s),
      onItem: (item) => emit(item.kind === 'count' ? 'countin' : 'hit', item),
    });
    bedHandle = played?.music || null;
    if (aborted()) throw new DOMException('Stopped', 'AbortError');
    emit('recording');
    await abortableDelay(SLACK_BEATS * spb * 1000, signal);
    const take = await rec.stop();
    bedHandle?.stop();
    if (aborted()) throw new DOMException('Stopped', 'AbortError');

    emit('uploading');
    const form = new FormData();
    form.append('audio', take.wav, `round-${round.id}.wav`);
    const countinStart = countinStartSeconds(started.startedAt, take.startTime);
    form.append('countin_start_s', String(countinStart));
    if (bed) {
      // The bed started at schedule time 0, i.e. with the first count-in click.
      form.append('backing_track_id', String(bed.track.id));
      form.append('music_start_s', String(countinStart));
      form.append('music_volume', String(bed.volume));
    }
    const res = await uploadWithRetry(`/api/rounds/${round.id}/recording`, form, {
      onWaiting: (n) => emit('waiting', n),
    });
    emit('scored', res);
    return res;
  } finally {
    bedHandle?.stop();
    rec.close();
  }
}

/**
 * "Measure music level": play the groove-only track alone through the room speaker for a few
 * loops while recording, so the server learns how the music sounds at the microphone.
 * The recording is analysed in memory on the server and never stored.
 */
export async function measureMusicLevel({ bed, bpm, volume, sessionId, onLevel, signal }) {
  const buffer = await loadTrack(bed);
  const loops = measureLoops(bed, bpm);
  const rec = await createRecorder({ onLevel });
  try {
    rec.start();
    let started = null;
    await playPattern({ events: [] }, bpm, {
      lengthBeats: loops * bed.loop_beats,
      playPattern: false,
      music: { track: bed, buffer, volume },
      onStart: (s) => (started = s),
    });
    await abortableDelay(300, signal); // let the last notes ring into the recording
    const take = await rec.stop();
    if (signal?.aborted) throw new DOMException('Stopped', 'AbortError');
    const form = new FormData();
    form.append('audio', take.wav, 'music-level.wav');
    form.append('bpm', String(bpm));
    form.append('music_start_s', String(countinStartSeconds(started.startedAt, take.startTime)));
    form.append('music_volume', String(volume));
    if (sessionId) form.append('session_id', String(sessionId));
    return await api(`/api/backing-tracks/${bed.id}/bleed`, { method: 'POST', body: form });
  } finally {
    rec.close();
  }
}
