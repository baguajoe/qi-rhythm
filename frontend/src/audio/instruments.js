import * as Tone from 'tone';

// Synthesized percussion voices. Each voice is a function (time, velocity) => void.
//
// Hook for real samples: set VOICE_SAMPLE_URLS[voice] to an R2 URL of an original Cubase-recorded
// one-shot and the kit will use a Tone.Player instead of the synth.
// TODO(phase-2): populate from Rhythm.reference_audio_key / an org sample kit once recorded.
export const VOICE_SAMPLE_URLS = { low: null, high: null, shaker: null, clap: null };

let kit = null;

export function getKit() {
  if (kit) return kit;
  const out = new Tone.Volume(-6).toDestination();

  const low = new Tone.MembraneSynth({
    pitchDecay: 0.03,
    octaves: 3,
    envelope: { attack: 0.001, decay: 0.35, sustain: 0, release: 0.1 },
  }).connect(out);
  const high = new Tone.MembraneSynth({
    pitchDecay: 0.015,
    octaves: 2,
    envelope: { attack: 0.001, decay: 0.15, sustain: 0, release: 0.05 },
  }).connect(out);
  const shakerFilter = new Tone.Filter(5000, 'highpass').connect(out);
  const shaker = new Tone.NoiseSynth({
    noise: { type: 'white' },
    envelope: { attack: 0.002, decay: 0.06, sustain: 0, release: 0.02 },
  }).connect(shakerFilter);
  const clapFilter = new Tone.Filter({ frequency: 1800, type: 'bandpass', Q: 1.2 }).connect(out);
  const clap = new Tone.NoiseSynth({
    noise: { type: 'pink' },
    envelope: { attack: 0.001, decay: 0.12, sustain: 0, release: 0.05 },
  }).connect(clapFilter);
  const click = new Tone.Synth({
    oscillator: { type: 'sine' },
    envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.02 },
  }).connect(out);

  const players = {};
  for (const [voice, url] of Object.entries(VOICE_SAMPLE_URLS)) {
    if (url) players[voice] = new Tone.Player(url).connect(out);
  }

  const synthVoices = {
    low: (t, v) => low.triggerAttackRelease('C2', '8n', t, v),
    high: (t, v) => high.triggerAttackRelease('G3', '16n', t, v),
    shaker: (t, v) => shaker.triggerAttackRelease('32n', t, v),
    clap: (t, v) => clap.triggerAttackRelease('16n', t, v),
  };

  kit = {
    output: out,
    play(voice, time, velocity = 0.8) {
      if (players[voice]?.loaded) players[voice].start(time);
      else (synthVoices[voice] || synthVoices.low)(time, velocity);
    },
    click(time, accent = false) {
      click.triggerAttackRelease(accent ? 'A5' : 'E5', '32n', time, accent ? 0.9 : 0.6);
    },
    setVolume(fraction) {
      out.volume.value = fraction <= 0 ? -Infinity : Tone.gainToDb(fraction);
    },
  };
  return kit;
}
