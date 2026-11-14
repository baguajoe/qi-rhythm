import * as Tone from 'tone';
import { buildSchedule } from './schedule.js';
import { getKit } from './instruments.js';

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
 * stay in sync with audio. Resolves with { startedAt } (AudioContext seconds of time 0) when done.
 */
export async function playPattern(
  pattern,
  bpm,
  { countIn = 0, lengthBeats, volume = 0.8, playPattern: withPattern = true, onItem, onStart } = {},
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
          else kit.play(item.voice, time, item.accent ? 1 : 0.75);
          if (onItem) draw.schedule(() => onItem(item), time);
        }, item.time + lead),
      );
    }
    const endAt = sched.duration + lead;
    const finish = () => {
      transport.stop();
      transport.cancel();
      active = null;
      resolve({ startedAt });
    };
    ids.push(transport.scheduleOnce((time) => draw.schedule(finish, time), endAt));
    // Transport time 0 maps to t0 (AudioContext seconds); every item sounds at t0 + lead + time.
    const t0 = Tone.now() + 0.05;
    const startedAt = t0 + lead;
    transport.start(t0);
    active = { finish };
    onStart?.({ startedAt, schedule: sched });
  });
}

export function stopPlayback() {
  const transport = Tone.getTransport();
  transport.stop();
  transport.cancel();
  if (active) {
    const { finish } = active;
    active = null;
    finish();
  }
}
