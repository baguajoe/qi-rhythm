"""Synthetic performance generator for testing the analysis engine.

Renders a beat-relative pattern into a mono recording, simulating what the classroom microphone
would capture: optional count-in click bleed, hits with timing jitter, missed and extra hits,
a global lateness offset, tempo changes, and background noise (white hiss + low rumble).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from .patterns import count_in_beats, length_beats, parse_events, seconds_per_beat


@dataclass
class SynthOptions:
    bpm: float = 90.0
    sr: int = 44100
    count_in: int | None = None  # defaults to the pattern's count_in_beats
    lead_in_s: float = 0.5  # recording time before the count-in downbeat
    tail_beats: float = 4.0  # slack recorded after the pattern ends
    jitter_ms: float = 0.0  # std-dev of per-hit timing jitter
    global_offset_ms: float = 0.0  # positive = team plays late
    latency_ms: float = 0.0  # simulated device round-trip latency
    tempo_scale: float = 1.0  # >1 = team plays uniformly faster than the reference
    tempo_drift: float = 0.0  # gradual: tempo ramps to (1 + drift) x by the end
    miss_count: int = 0
    miss_indices: list[int] | None = None
    extra_count: int = 0
    hit_level: float = 0.7
    level_jitter: float = 0.0  # +/- fraction of hit_level
    noise_level: float = 0.0  # white-noise RMS (full scale = 1.0)
    rumble_level: float = 0.0  # low-frequency rumble RMS
    count_in_clicks: bool = False  # simulate speaker bleed of the count-in
    click_level: float = 0.3
    voice: str | None = None  # override every event's voice
    # Backing-track ("bed") bleed: a looping groove heard by the room mic under the team.
    bed: dict | None = None  # {"events": [{"beat", "voice"}], "loop_beats": 4} (see DEFAULT_BED)
    bed_level: float = 0.0  # peak gain of the bed's drum hits (0 = no bed)
    bed_pad_level: float = 0.0  # RMS of the bed's sustained bass/chord pad
    bed_offset_ms: float = 0.0  # bed start relative to the count-in downbeat
    team_silent: bool = False  # render only count-in/bed (e.g. a "Measure music level" pass)
    seed: int = 0


@dataclass
class SynthResult:
    audio: np.ndarray
    sr: int
    countin_start_s: float  # seconds from recording start to count-in downbeat
    hit_times: list[float] = field(default_factory=list)  # actual rendered hit onsets
    missed_indices: list[int] = field(default_factory=list)
    extra_times: list[float] = field(default_factory=list)
    bed_start_s: float | None = None  # scheduled bed beat 0 in recording time (before latency)
    bed_times: list[float] = field(default_factory=list)  # rendered bed drum hits

    def write(self, path) -> None:
        write_wav(path, self.audio, self.sr)


# ---------------------------------------------------------------- timbres


def _bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    hi = min(hi, 0.45 * sr)
    sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    return sosfilt(sos, x)


def _drum(sr: int, f0: float, decay: float, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * 0.45)
    t = np.arange(n) / sr
    freq = f0 * (1.0 + 0.6 * np.exp(-t / 0.015))  # slight pitch drop, like a hand drum
    body = np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-t / decay)
    slap = rng.standard_normal(n) * np.exp(-t / 0.004) * 0.6
    attack = np.minimum(1.0, t / 0.001)
    out = (body + slap) * attack
    return out / np.max(np.abs(out))


def _shaker(sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * 0.12)
    t = np.arange(n) / sr
    noise = _bandpass(rng.standard_normal(n), sr, 3000, 9000)
    env = np.minimum(1.0, t / 0.002) * np.exp(-t / 0.035)
    out = noise * env
    return out / np.max(np.abs(out))


def _clap(sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * 0.2)
    t = np.arange(n) / sr
    noise = _bandpass(rng.standard_normal(n), sr, 900, 4500)
    env = np.zeros(n)
    for k, start in enumerate((0.0, 0.009, 0.018)):
        tt = np.clip(t - start, 0, None)
        env += (t >= start) * np.exp(-tt / (0.004 if k < 2 else 0.05)) * (1.0 - 0.15 * k)
    out = noise * env
    return out / np.max(np.abs(out))


def _click(sr: int) -> np.ndarray:
    n = int(sr * 0.03)
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * 1000 * t) * np.exp(-t / 0.008)


def _hat(sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * 0.06)
    t = np.arange(n) / sr
    out = _bandpass(rng.standard_normal(n), sr, 6000, 12000) * np.exp(-t / 0.012)
    return out / np.max(np.abs(out))


def _snare(sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * 0.25)
    t = np.arange(n) / sr
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    noise = _bandpass(rng.standard_normal(n), sr, 1500, 8000) * np.exp(-t / 0.06)
    out = (0.6 * tone + noise) * np.minimum(1.0, t / 0.001)
    return out / np.max(np.abs(out))


def voice_sample(voice: str, sr: int, rng: np.random.Generator) -> np.ndarray:
    if voice in ("low", "kick"):
        return _drum(sr, 110.0, 0.12, rng)
    if voice == "high":
        return _drum(sr, 300.0, 0.07, rng)
    if voice == "shaker":
        return _shaker(sr, rng)
    if voice == "clap":
        return _clap(sr, rng)
    if voice == "hat":
        return _hat(sr, rng)
    if voice == "snare":
        return _snare(sr, rng)
    raise ValueError(f"unknown voice {voice!r}")


# A typical backing-track groove: kick on 1 and 3, snare on 2 and 4, eighth-note hi-hats.
# Every eighth note coincides with a hat, so it is a hard case for telling claps from the bed.
DEFAULT_BED = {
    "loop_beats": 4,
    "events": [
        {"beat": 0, "voice": "kick"},
        {"beat": 2, "voice": "kick"},
        {"beat": 1, "voice": "snare"},
        {"beat": 3, "voice": "snare"},
        *({"beat": b / 2, "voice": "hat", "gain": 0.45} for b in range(8)),
    ],
}


# ---------------------------------------------------------------- rendering


def _render_bed(buf: np.ndarray, start: float, spb: float, opts: SynthOptions, rng) -> list[float]:
    """Loop the bed groove from ``start`` to the end of the buffer (speaker bleed into the mic)."""
    sr = opts.sr
    bed = opts.bed or DEFAULT_BED
    loop = float(bed.get("loop_beats", 4))
    end_s = len(buf) / sr
    times = []
    if opts.bed_level > 0:
        samples = {v: voice_sample(v, sr, rng) for v in sorted({e["voice"] for e in bed["events"]})}
        k = 0
        while start + k * loop * spb < end_s:
            for ev in bed["events"]:
                t = start + (k * loop + float(ev["beat"])) * spb
                if t < end_s:
                    _mix(buf, samples[ev["voice"]], t, sr, opts.bed_level * ev.get("gain", 1.0))
                    times.append(t)
            k += 1
    if opts.bed_pad_level > 0:
        # Sustained bass + chord pad from the bed's start, re-articulated softly every bar.
        n0 = max(0, int(start * sr))
        t = np.arange(len(buf) - n0) / sr
        pad = (
            np.sin(2 * np.pi * 98 * t)
            + 0.6 * np.sin(2 * np.pi * 196 * t)
            + 0.4 * np.sin(2 * np.pi * 247 * t)
            + 0.3 * np.sin(2 * np.pi * 294 * t)
        )
        swell = 0.75 + 0.25 * np.cos(2 * np.pi * t / (loop * spb))
        pad *= swell
        buf[n0:] += pad / (np.std(pad) + 1e-12) * opts.bed_pad_level
    return sorted(times)


def _performed_offset(beat: float, spb: float, length: float, opts: SynthOptions) -> float:
    """Seconds from pattern start at which the performer plays ``beat``."""
    if opts.tempo_drift:
        d = opts.tempo_drift
        t = spb * length / d * np.log1p(d * beat / length)
    else:
        t = beat * spb
    return t / opts.tempo_scale


def _mix(buf: np.ndarray, sample: np.ndarray, t: float, sr: int, gain: float) -> None:
    start = int(round(t * sr))
    if start >= len(buf) or start + len(sample) <= 0:
        return
    s0 = max(0, -start)
    end = min(len(buf), start + len(sample))
    buf[start + s0 : end] += gain * sample[s0 : end - start]


def render(pattern: dict, opts: SynthOptions | None = None) -> SynthResult:
    opts = opts or SynthOptions()
    rng = np.random.default_rng(opts.seed)
    sr = opts.sr
    spb = seconds_per_beat(opts.bpm)
    events = parse_events(pattern)
    n_count = opts.count_in if opts.count_in is not None else count_in_beats(pattern)
    length = length_beats(pattern)

    duration = opts.lead_in_s + (n_count + length + opts.tail_beats) * spb + 0.5
    buf = np.zeros(int(duration * sr))
    latency = opts.latency_ms / 1000.0
    pattern_start = opts.lead_in_s + n_count * spb + latency

    if opts.count_in_clicks:
        click = _click(sr)
        for k in range(n_count):
            _mix(buf, click, opts.lead_in_s + k * spb + latency, sr, opts.click_level)

    if opts.miss_indices is not None:
        missed = sorted(set(opts.miss_indices))
    elif opts.miss_count:
        missed = sorted(rng.choice(len(events), size=opts.miss_count, replace=False).tolist())
    else:
        missed = []

    bed_start = None
    bed_times: list[float] = []
    if opts.bed_level > 0 or opts.bed_pad_level > 0:
        bed_start = opts.lead_in_s + opts.bed_offset_ms / 1000.0  # scheduled (like countin_start_s)
        bed_times = _render_bed(buf, bed_start + latency, spb, opts, rng)

    hit_times = []
    for ev in events:
        if opts.team_silent:
            break
        if ev.index in missed:
            continue
        t = pattern_start + _performed_offset(ev.beat, spb, length, opts)
        t += opts.global_offset_ms / 1000.0 + rng.normal(0.0, opts.jitter_ms / 1000.0)
        level = opts.hit_level * (1.0 + rng.uniform(-opts.level_jitter, opts.level_jitter))
        if ev.accent:
            level *= 1.15
        _mix(buf, voice_sample(opts.voice or ev.voice, sr, rng), t, sr, level)
        hit_times.append(t)

    extra_times: list[float] = []
    span_start = pattern_start
    span_end = pattern_start + length * spb
    attempts = 0
    while not opts.team_silent and len(extra_times) < opts.extra_count and attempts < 1000:
        attempts += 1
        t = rng.uniform(span_start, span_end)
        if all(abs(t - h) > 0.15 for h in hit_times + extra_times):
            extra_times.append(t)
            voice = opts.voice or events[int(rng.integers(len(events)))].voice
            _mix(buf, voice_sample(voice, sr, rng), t, sr, opts.hit_level)

    if opts.noise_level:
        buf += rng.standard_normal(len(buf)) * opts.noise_level
    if opts.rumble_level:
        sos = butter(2, 60, btype="low", fs=sr, output="sos")
        rumble = sosfilt(sos, rng.standard_normal(len(buf)))
        rumble += 0.5 * np.sin(2 * np.pi * 50 * np.arange(len(buf)) / sr) * np.std(rumble)
        buf += rumble / (np.std(rumble) + 1e-12) * opts.rumble_level

    audio = np.clip(buf, -1.0, 1.0).astype(np.float32)
    return SynthResult(
        audio=audio,
        sr=sr,
        countin_start_s=opts.lead_in_s,
        hit_times=sorted(hit_times),
        missed_indices=missed,
        extra_times=sorted(extra_times),
        bed_start_s=bed_start,
        bed_times=bed_times,
    )


def write_wav(path, audio: np.ndarray, sr: int) -> None:
    sf.write(str(path), audio, sr, subtype="PCM_16")
