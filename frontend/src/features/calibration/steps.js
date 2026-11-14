import { api } from '../../lib/api.js';

export const NOISE_SECONDS = 5;
export const SENSITIVITY_SECONDS = 6;
export const LATENCY_CLICKS = 8;
export const LATENCY_BPM = 80;

export async function uploadStep(step, wav, fields = {}) {
  const form = new FormData();
  form.append('audio', wav, `${step}.wav`);
  for (const [k, v] of Object.entries(fields))
    form.append(k, typeof v === 'string' ? v : JSON.stringify(v));
  return api(`/api/calibration/analyze/${step}`, { method: 'POST', body: form });
}

/** Click times relative to the start of the recording, in seconds. */
export function clickTimesRelative(playStartedAt, schedule, recordingStartTime) {
  return schedule.items
    .filter((i) => i.kind === 'count')
    .map((i) => playStartedAt + i.time - recordingStartTime);
}
