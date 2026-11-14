import * as Tone from 'tone';
import { api } from '../lib/api.js';

// Backing tracks (an organization's own loops, e.g. exported from Cubase).
//
// "full" = groove with the pattern audible (played while the team listens);
// "bed"  = groove only (played under the team's turn).
// A track is started at the same AudioContext time as Transport position 0 of the count-in /
// pattern schedule, so the music, the beat visualizer, the count-in and the scoring grid share
// one clock. Loops other than the round's tempo are time-stretched (pitch kept) with GrainPlayer.

/** Which track to play, and whether to silence the synthesized pattern, for a phase. */
export function chooseMusic(music, phase, musicOn = true) {
  if (!musicOn || !music) return null;
  if (phase === 'listen') {
    if (music.full) return { track: music.full, muteHits: true };
    if (music.bed) return { track: music.bed, muteHits: false }; // groove + synthesized pattern
    return null;
  }
  if (phase === 'turn' && music.bed) return { track: music.bed, muteHits: false };
  return null;
}

/** Playback parameters for a loop at the round's tempo. */
export function musicPlan(track, bpm, bufferDuration = Infinity) {
  const rate = bpm / track.bpm;
  return {
    rate,
    stretch: Math.abs(rate - 1) > 0.002,
    loopEnd: Math.min(track.loop_seconds, bufferDuration),
  };
}

/** Seconds of bed to play for a "Measure music level" pass: at least 2 loops and ~8 s. */
export function measureLoops(track, bpm, minSeconds = 8) {
  const loopSeconds = (track.loop_beats * 60) / bpm;
  return Math.max(2, Math.ceil(minSeconds / loopSeconds));
}

const cache = new Map();

/** Fetch + decode a track's WAV once per revision. */
export function loadTrack(track) {
  const key = `${track.id}:${track.rev || ''}`;
  if (!cache.has(key)) {
    const p = (async () => {
      const res = await api(track.audio_path, { raw: true });
      if (!res.ok) throw new Error('The backing music could not be loaded.');
      const audio = await Tone.getContext().decodeAudioData(await res.arrayBuffer());
      return new Tone.ToneAudioBuffer(audio);
    })();
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return cache.get(key);
}

// Created on first playback (after a user gesture); the slider value is remembered until then.
let bus = null;
let busVolume = 0.6;
const toDb = (fraction) => (fraction <= 0 ? -Infinity : Tone.gainToDb(fraction));

function musicBus() {
  if (!bus) bus = new Tone.Volume(toDb(busVolume)).toDestination();
  return bus;
}

/** Music slider (0-1). Applies immediately to music that is already playing. */
export function setMusicVolume(fraction) {
  busVolume = fraction;
  if (bus) bus.volume.value = toDb(fraction);
}

const playing = new Set();

/**
 * Start a looping track at AudioContext time `when` (= Transport position 0 of the schedule).
 * Returns a handle with stop(); stopAllMusic() stops every handle (the Stop button).
 */
export function startMusic({ buffer, track, volume }, bpm, when) {
  setMusicVolume(volume);
  const plan = musicPlan(track, bpm, buffer.duration);
  const player = plan.stretch
    ? new Tone.GrainPlayer({ url: buffer, grainSize: 0.1, overlap: 0.05 })
    : new Tone.Player(buffer);
  player.loop = true;
  player.loopStart = 0;
  player.loopEnd = plan.loopEnd;
  player.playbackRate = plan.rate;
  player.connect(musicBus());
  player.start(when);
  const handle = {
    stop(fade = 0.08) {
      if (!playing.has(handle)) return;
      playing.delete(handle);
      const now = Tone.now();
      try {
        player.volume.rampTo(-Infinity, fade, now);
        player.stop(now + fade);
      } catch {
        /* already stopped */
      }
      setTimeout(() => player.dispose(), (fade + 0.2) * 1000);
    },
  };
  playing.add(handle);
  return handle;
}

export function stopAllMusic() {
  for (const h of [...playing]) h.stop();
}
