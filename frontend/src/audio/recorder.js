import * as Tone from 'tone';
import { concatFloat32, encodeWav } from './wav.js';

// Microphone capture via AudioWorklet on the SAME AudioContext as Tone.js playback, so recording
// timestamps share the playback clock. Echo cancellation, noise suppression and auto gain are
// OFF: they smear or remove percussive transients.
export const MIC_CONSTRAINTS = {
  audio: {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
    channelCount: 1,
  },
};

const WORKLET = `
class QiCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.recording = false;
    this.levelEvery = Math.round(sampleRate / 30);
    this.acc = 0; this.n = 0;
    this.port.onmessage = (e) => { this.recording = e.data === 'start' ? true : e.data === 'stop' ? false : this.recording; if (e.data === 'stop') this.port.postMessage({ type: 'stopped' }); };
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) { this.acc += ch[i] * ch[i]; }
    this.n += ch.length;
    if (this.n >= this.levelEvery) { this.port.postMessage({ type: 'level', rms: Math.sqrt(this.acc / this.n) }); this.acc = 0; this.n = 0; }
    if (this.recording) this.port.postMessage({ type: 'chunk', frame: currentFrame, data: ch.slice(0) });
    return true;
  }
}
registerProcessor('qi-capture', QiCapture);
`;

let moduleLoaded = false;

export async function createRecorder({ onLevel } = {}) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot use a microphone. Try Chrome or Edge.');
  }
  await Tone.start();
  const ctx = Tone.getContext();
  if (!moduleLoaded) {
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
    await ctx.addAudioWorkletModule(url);
    moduleLoaded = true;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS);
  } catch {
    throw new Error('We need permission to use the microphone. Please allow it and try again.');
  }
  const source = ctx.createMediaStreamSource(stream);
  const node = ctx.createAudioWorkletNode('qi-capture', { numberOfInputs: 1, numberOfOutputs: 1 });
  const sink = ctx.createGain();
  sink.gain.value = 0; // keep the node pulled by the graph without making sound
  source.connect(node);
  node.connect(sink);
  sink.connect(ctx.rawContext.destination);

  const sampleRate = ctx.sampleRate;
  let chunks = [];
  let firstFrame = null;
  let onStopped = null;

  node.port.onmessage = (e) => {
    const msg = e.data;
    if (msg.type === 'level') onLevel?.(msg.rms);
    else if (msg.type === 'chunk') {
      if (firstFrame === null) firstFrame = msg.frame;
      chunks.push(msg.data);
    } else if (msg.type === 'stopped') onStopped?.();
  };

  return {
    sampleRate,
    /** Begin capturing. Returns the AudioContext time (s) at which capture was requested. */
    start() {
      chunks = [];
      firstFrame = null;
      node.port.postMessage('start');
      return ctx.rawContext.currentTime;
    },
    /** Stop and return { wav, samples, sampleRate, startTime } (startTime = ctx seconds of sample 0). */
    stop() {
      return new Promise((resolve) => {
        onStopped = () => {
          const samples = concatFloat32(chunks);
          const startTime =
            firstFrame === null ? ctx.rawContext.currentTime : firstFrame / sampleRate;
          resolve({ wav: encodeWav(samples, sampleRate), samples, sampleRate, startTime });
        };
        node.port.postMessage('stop');
      });
    },
    close() {
      try {
        source.disconnect();
        node.disconnect();
        sink.disconnect();
      } catch {
        /* already disconnected */
      }
      stream.getTracks().forEach((t) => t.stop());
    },
  };
}

/** Convenience: record for a fixed number of seconds. */
export async function recordFor(seconds, { onLevel, onTick } = {}) {
  const rec = await createRecorder({ onLevel });
  try {
    rec.start();
    const start = performance.now();
    await new Promise((resolve) => {
      const id = setInterval(() => {
        const left = seconds - (performance.now() - start) / 1000;
        onTick?.(Math.max(0, Math.ceil(left)));
        if (left <= 0) {
          clearInterval(id);
          resolve();
        }
      }, 100);
    });
    return await rec.stop();
  } finally {
    rec.close();
  }
}
