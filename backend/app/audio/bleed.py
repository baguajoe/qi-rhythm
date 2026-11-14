"""Backing-track bleed: the room microphone hears the music bed under the team's playing.

"Measure music level" records the bed alone through the room speaker. ``measure_bleed`` turns that
recording into a ``BleedProfile``: the bed's continuous level (raises the noise gate) and the
beat positions and levels of its own transients (kick, snare, hats). During a team turn the bed is
locked to the same beat grid, so ``bleed_mask`` predicts when each of those transients reaches the
mic; the onset detector then ignores an onset that lines up with one unless it is clearly louder
than the music alone (a team hit landing on the same beat).

Positions are stored in beats with device latency removed, so a profile measured at one tempo and
volume can be reused at another (levels scale with the music volume).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from .onset import (
    OnsetParams,
    band_levels_db,
    detect_onsets,
    frame_rms_db,
    highpass,
    load_audio,
)

MATCH_WINDOW_S = 0.035  # clustering tolerance when folding measured transients onto the loop
MIN_LOOPS_HEARD = 0.5  # a transient must recur in at least this share of the measured loops
FLOOR_PERCENTILE = 30.0  # music level *between* its drum hits (the hits are handled separately)


@dataclass
class BleedProfile:
    loop_beats: float
    floor_db: float  # continuous music level between its drum hits (dBFS short-term RMS)
    music_volume: float  # instructor's music slider (0-1) when measured
    bpm: float
    transients: list[dict] = field(default_factory=list)  # {beat, level_db, bands, seen}
    loops_measured: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> BleedProfile:
        return cls(
            loop_beats=float(d["loop_beats"]),
            floor_db=float(d["floor_db"]),
            music_volume=float(d["music_volume"]),
            bpm=float(d["bpm"]),
            transients=list(d.get("transients", [])),
            loops_measured=float(d.get("loops_measured", 0.0)),
        )


def volume_gain_db(measured_volume: float, played_volume: float) -> float:
    """Level change at the mic when the music slider moves from measured to played."""
    if played_volume <= 0:
        return -120.0
    return 20.0 * math.log10(played_volume / max(measured_volume, 1e-3))


def _circular_clusters(pos: np.ndarray, loop: float, tol: float) -> list:
    """Group loop positions (beats) that are within ``tol`` of each other, wrapping at ``loop``."""
    if len(pos) == 0:
        return []
    order = np.argsort(pos)
    pos = pos[order]
    groups: list[list[int]] = [[0]]
    for i in range(1, len(pos)):
        if pos[i] - pos[groups[-1][-1]] <= tol:
            groups[-1].append(i)
        else:
            groups.append([i])
    # Merge the last group into the first when they meet across the loop boundary.
    if len(groups) > 1 and (pos[groups[0][0]] + loop) - pos[groups[-1][-1]] <= tol:
        groups[0] = groups.pop() + groups[0]
    out = []
    for g in groups:
        p = pos[g].copy()
        if p.max() - p.min() > loop / 2:  # wrapped group: unwrap before averaging
            p[p > loop / 2] -= loop
        out.append((float(np.median(p)) % loop, order[g]))
    return out


def measure_bleed(
    source,
    *,
    bpm: float,
    bed_start_s: float,
    loop_beats: float,
    latency_ms: float = 0.0,
    music_volume: float = 1.0,
    sr: int | None = None,
) -> BleedProfile:
    """Analyse a recording of the bed alone (no one playing) through the room speaker."""
    y, sr = load_audio(source, sr)
    spb = 60.0 / bpm
    start = bed_start_s + latency_ms / 1000.0
    i0 = max(0, int(start * sr))
    yh = highpass(y, sr, 70.0)  # the same signal detect_onsets measures bands on
    music = yh[i0:]
    floor_db = (
        float(np.percentile(frame_rms_db(music), FLOOR_PERCENTILE))
        if len(music) and np.any(music)
        else -120.0
    )

    # Sensitive detection: catch every bed transient the real analysis could mistake for a hit.
    res = detect_onsets(y, sr, OnsetParams(gate_margin_db=3.0, relative_gate_db=60.0))
    heard = [o for o in res.onsets if o.time_s >= start - MATCH_WINDOW_S]
    loops = max(0.0, (len(y) / sr - start) / (loop_beats * spb))
    if not heard or loops <= 0:
        return BleedProfile(loop_beats, round(floor_db, 1), music_volume, bpm, [], round(loops, 2))

    pos = np.array([((o.time_s - start) / spb) % loop_beats for o in heard])
    lev = np.array([o.level_db for o in heard])
    bands = np.array([band_levels_db(yh, sr, o.time_s) for o in heard])
    need = max(1, int(math.floor(MIN_LOOPS_HEARD * loops)))
    transients = []
    for beat, idx in _circular_clusters(pos, loop_beats, MATCH_WINDOW_S / spb):
        if len(idx) >= need:
            transients.append(
                {
                    "beat": round(beat, 4),
                    "level_db": round(float(np.percentile(lev[idx], 75)), 1),
                    # Loudest-ish take of each band, so a soft repeat of the music never passes.
                    "bands": [round(float(v), 1) for v in np.percentile(bands[idx], 90, axis=0)],
                    "seen": int(len(idx)),
                }
            )
    transients.sort(key=lambda t: t["beat"])
    return BleedProfile(
        loop_beats=float(loop_beats),
        floor_db=round(floor_db, 1),
        music_volume=float(music_volume),
        bpm=float(bpm),
        transients=transients,
        loops_measured=round(loops, 2),
    )


def bleed_mask(
    profile: BleedProfile,
    *,
    bpm: float,
    bed_start_s: float,
    duration_s: float,
    latency_ms: float = 0.0,
    music_volume: float | None = None,
) -> list[tuple[float, list[float]]]:
    """Predicted (time_s, band_levels_db) of every bed transient in a take of ``duration_s``."""
    if not profile.transients:
        return []
    spb = 60.0 / bpm
    gain = volume_gain_db(
        profile.music_volume, profile.music_volume if music_volume is None else music_volume
    )
    start = bed_start_s + latency_ms / 1000.0
    loop_s = profile.loop_beats * spb
    out = []
    k = 0
    while start + k * loop_s < duration_s + loop_s:
        for tr in profile.transients:
            t = start + (k * profile.loop_beats + tr["beat"]) * spb
            if 0 <= t <= duration_s:
                out.append((round(t, 5), [b + gain for b in tr["bands"]]))
        k += 1
    return out


def bleed_params(
    profile: BleedProfile,
    base: OnsetParams,
    *,
    bpm: float,
    bed_start_s: float,
    duration_s: float,
    latency_ms: float = 0.0,
    music_volume: float | None = None,
) -> OnsetParams:
    """Onset parameters for a take recorded with the bed playing."""
    vol = profile.music_volume if music_volume is None else music_volume
    gain = volume_gain_db(profile.music_volume, vol)
    floor = profile.floor_db + gain
    base.noise_floor_db = floor if base.noise_floor_db is None else max(base.noise_floor_db, floor)
    base.bleed = bleed_mask(
        profile,
        bpm=bpm,
        bed_start_s=bed_start_s,
        duration_s=duration_s,
        latency_ms=latency_ms,
        music_volume=vol,
    )
    return base
