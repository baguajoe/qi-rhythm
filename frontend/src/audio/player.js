import * as Tone from 'tone';
import { buildSchedule } from './schedule.js';
import { getKit } from './instruments.js';
import { startMusic, stopAllMusic } from './music.js';

/** Must be called from a user gesture (button press) before any playback. */
export async function unlockAudio() {
  await Tone.start();
  return Tone.getContext().rawContext;
}

export function audioContext() {
  return Tone.getContext().rawContext;
}

let active = null;

/**
 * Play a schedule (count-in and/or pattern) on Tone.Transport, sample-accurately.
 * `onItem(item)` fires on the animation frame closest to each sound (via Tone.Draw) so visuals
 * stay in sync with audio. Resolves with { startedAt, music } when done (startedAt =
 * AudioContext seconds of schedule time 0).
 *
 * `music` ({ buffer, track, volume }) starts a backing track exactly at schedule time 0 (the
 * first count-in click, or the pattern's first beat when there is no count-in). It stops with
 * the schedule unless `keepMusic` is set, in which case the caller stops the returned handle.
 * `muteHits` keeps the pattern's visual cues but silences the synthesized drums (the "full"
 * backing track already plays the pattern).
 */
export async function playPattern(
  pattern,
  bpm,
  {
    countIn = 0,
    lengthBeats,
    volume = 0.8,
    playPattern: withPattern = true,
    muteHits = false,
    music = null,
    keepMusic = false,
    onItem,
    onStart,
  } = {},
) {
  await unlockAudio();
  stopPlayback();
  const kit = getKit();
  kit.setVolume(volume);
  const transport = Tone.getTransport();
  const draw = Tone.getDraw();
  const sched = buildSchedule(withPattern ? pattern : { events: [] }, bpm, {
    countIn,
    lengthBeats,
  });
  const ids = [];
  const lead = 0.1; // seconds of scheduling headroom

  return new Promise((resolve) => {
    transport.cancel();
    transport.position = 0;
    for (const item of sched.items) {
      ids.push(
        transport.schedule((time) => {
          if (item.kind === 'count') kit.click(time, item.accent);
          else if (item.kind === 'hit' && !muteHits)
            kit.play(item.voice, time, item.accent ? 1 : 0.75);
          // 'go' is silent: a visual cue only.
          if (onItem) draw.schedule(() => onItem(item), time);
        }, item.time + lead),
      );
    }
    const endAt = sched.duration + lead;
    let musicHandle = null;
    const finish = () => {
      transport.stop();
      transport.cancel();
      active = null;
      if (musicHandle && !keepMusic) musicHandle.stop();
      resolve({ startedAt, music: musicHandle });
    };
    ids.push(transport.scheduleOnce((time) => draw.schedule(finish, time), endAt));
    // Transport time 0 maps to t0 (AudioContext seconds); every item sounds at t0 + lead + time.
    const t0 = Tone.now() + 0.05;
    const startedAt = t0 + lead;
    if (music) musicHandle = startMusic(music, bpm, startedAt);
    transport.start(t0);
    active = { finish };
    onStart?.({ startedAt, schedule: sched });
  });
}

export function stopPlayback() {
  stopAllMusic();
  const transport = Tone.getTransport();
  transport.stop();
  transport.cancel();
  if (active) {
    const { finish } = active;
    active = null;
    finish();
  }
}
