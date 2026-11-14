// Pure timing helpers shared by the player, the round flow, and the visualizers.

export const MIN_TEMPO_PCT = 50;
export const MAX_TEMPO_PCT = 120;

export function effectiveBpm(baseBpm, tempoPct = 100) {
  const pct = Math.min(MAX_TEMPO_PCT, Math.max(MIN_TEMPO_PCT, tempoPct));
  return Math.round(baseBpm * pct) / 100;
}

export function sortedEvents(pattern) {
  return [...(pattern?.events || [])]
    .map((e) => ({ ...e, beat: Number(e.beat) }))
    .sort((a, b) => a.beat - b.beat)
    .map((e, index) => ({ ...e, index }));
}

export function patternLengthBeats(pattern, lengthBeats) {
  if (lengthBeats) return lengthBeats;
  if (pattern?.length_beats) return pattern.length_beats;
  const last = Math.max(0, ...sortedEvents(pattern).map((e) => e.beat));
  return (Math.floor(last / 4) + 1) * 4;
}

/**
 * Build a play schedule (seconds, relative to start) for an optional count-in followed by the
 * pattern. Each item: { kind: 'count'|'go'|'hit', time, index, voice, accent, countNumber }.
 * After a count-in, a silent 'go' cue sits exactly on the pattern's first beat (one beat after
 * the final count): the moment the team starts playing and "Your turn!" must appear.
 */
export function buildSchedule(pattern, bpm, { countIn = 0, lengthBeats } = {}) {
  const spb = 60 / bpm;
  const items = [];
  for (let k = 0; k < countIn; k += 1) {
    items.push({
      kind: 'count',
      time: k * spb,
      index: k,
      countNumber: countIn - k,
      accent: k === 0,
    });
  }
  const start = countIn * spb;
  if (countIn > 0) items.push({ kind: 'go', time: start, index: -1 });
  for (const e of sortedEvents(pattern)) {
    items.push({
      kind: 'hit',
      time: start + e.beat * spb,
      index: e.index,
      voice: e.voice,
      accent: !!e.accent,
    });
  }
  const duration = start + patternLengthBeats(pattern, lengthBeats) * spb;
  return { items, duration, patternStart: start, secondsPerBeat: spb };
}

/** Seconds of audio to record: count-in + pattern + one bar of slack (spec 4.1). */
export function recordingSeconds(pattern, bpm, lengthBeats) {
  const spb = 60 / bpm;
  const countIn = pattern?.count_in_beats ?? 4;
  return (countIn + patternLengthBeats(pattern, lengthBeats) + 4) * spb;
}

export function pickSurprise(rhythms, random = Math.random) {
  if (!rhythms?.length) return null;
  return rhythms[Math.floor(random() * rhythms.length) % rhythms.length];
}
