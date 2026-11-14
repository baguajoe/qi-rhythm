import { concatFloat32, encodeWav, encodeWavBuffer, rmsDb } from './wav.js';

test('encodeWav returns a WAV blob', () => {
  const blob = encodeWav(new Float32Array(10), 44100);
  expect(blob.type).toBe('audio/wav');
  expect(blob.size).toBe(64);
});

test('encodes a valid 16-bit mono WAV header and samples', () => {
  const samples = new Float32Array([0, 0.5, -0.5, 1, -1, 2]);
  const view = new DataView(encodeWavBuffer(samples, 48000));
  const str = (o, n) =>
    String.fromCharCode(...Array.from({ length: n }, (_, i) => view.getUint8(o + i)));
  expect(str(0, 4)).toBe('RIFF');
  expect(str(8, 4)).toBe('WAVE');
  expect(view.getUint16(20, true)).toBe(1);
  expect(view.getUint16(22, true)).toBe(1);
  expect(view.getUint32(24, true)).toBe(48000);
  expect(view.getUint16(34, true)).toBe(16);
  expect(view.getUint32(40, true)).toBe(12);
  expect(view.byteLength).toBe(44 + 12);
  expect(view.getInt16(46, true)).toBe(16383);
  expect(view.getInt16(48, true)).toBe(-16384);
  expect(view.getInt16(54, true)).toBe(32767); // clipped
});

test('concatFloat32 joins chunks', () => {
  expect(Array.from(concatFloat32([new Float32Array([1, 2]), new Float32Array([3])]))).toEqual([
    1, 2, 3,
  ]);
});

test('rmsDb', () => {
  expect(rmsDb(new Float32Array([1, -1]))).toBeCloseTo(0, 3);
  expect(rmsDb(new Float32Array([]))).toBe(-120);
});
