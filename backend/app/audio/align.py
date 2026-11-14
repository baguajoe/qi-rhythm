"""Align detected strikes with the reference pattern's expected strike times.

Steps:
1. Convert beat-relative events to expected clip times (tempo, count-in, recording offset,
   calibrated device latency).
2. Restrict detected onsets to an analysis window around the pattern; anything earlier is
   count-in bleed or warm-up playing and is ignored (not penalised).
3. Fit the team's grid: a bounded tempo scale (0.8-1.25x) and a global offset (median
   nearest-neighbour difference). A team that is consistently a little late, or plays the right
   pattern a bit fast, is matched to the right events instead of being penalised on every hit;
   the tempo difference is scored separately by tempo consistency.
4. One-to-one matching with the Hungarian algorithm inside the tolerance window.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from .patterns import PatternEvent, count_in_beats, length_beats, parse_events, seconds_per_beat

OUT_OF_WINDOW_COST = 1e6
DEFAULT_MAX_OFFSET_S = 0.2
TEMPO_SCALES = np.round(np.arange(0.80, 1.2501, 0.005), 3)  # performed / reference duration
SCALE_BIAS = 2.0  # prefer scale 1.0 unless another scale clearly matches better


@dataclass
class ExpectedEvent:
    index: int
    beat: float
    voice: str
    time_s: float


@dataclass
class MatchedPair:
    expected_index: int
    detected_index: int
    expected_s: float
    detected_s: float
    error_ms: float  # after global-offset correction; positive = late


@dataclass
class Alignment:
    expected: list[ExpectedEvent]
    detected_s: list[float]  # in-window detected onset times
    matched: list[MatchedPair]
    missed: list[int]  # expected indices with no partner
    extras: list[int]  # detected indices (into detected_s) with no partner
    ignored_s: list[float] = field(default_factory=list)  # outside the analysis window
    global_offset_ms: float = 0.0
    tempo_scale: float = 1.0  # fitted performed/reference duration ratio (<1 = played faster)
    window_s: tuple[float, float] = (0.0, 0.0)
    pattern_span_s: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict:
        return asdict(self)


def expected_times(
    events: list[PatternEvent],
    *,
    bpm: float,
    count_in: int,
    countin_start_s: float,
    latency_ms: float = 0.0,
) -> list[ExpectedEvent]:
    """Expected clip time for each event.

    ``countin_start_s`` is the time from the start of the recording to the first count-in beat.
    ``latency_ms`` is the calibrated device round-trip offset (positive = sound arrives late).
    """
    spb = seconds_per_beat(bpm)
    start = countin_start_s + count_in * spb + latency_ms / 1000.0
    return [ExpectedEvent(e.index, e.beat, e.voice, start + e.beat * spb) for e in events]


def estimate_global_offset(
    expected: np.ndarray, detected: np.ndarray, radius_s: float, max_offset_s: float
) -> float:
    """Median nearest-neighbour difference (detected - expected), clamped to +/- max_offset_s."""
    if len(expected) == 0 or len(detected) == 0:
        return 0.0
    diffs = []
    for t in expected:
        j = int(np.argmin(np.abs(detected - t)))
        d = detected[j] - t
        if abs(d) <= radius_s:
            diffs.append(d)
    # Need enough support that the offset reflects the team, not one stray hit.
    if len(diffs) < max(2, int(np.ceil(0.3 * len(expected)))):
        return 0.0
    return float(np.clip(np.median(diffs), -max_offset_s, max_offset_s))


def match(expected: np.ndarray, detected: np.ndarray, tolerance_s: float):
    """One-to-one matching minimising total |error| within ``tolerance_s``.

    Returns (pairs [(exp_idx, det_idx)], missed exp indices, extra det indices).
    """
    n_e, n_d = len(expected), len(detected)
    if n_e == 0 or n_d == 0:
        return [], list(range(n_e)), list(range(n_d))
    cost = np.abs(expected[:, None] - detected[None, :])
    cost = np.where(cost <= tolerance_s, cost, OUT_OF_WINDOW_COST)
    rows, cols = linear_sum_assignment(cost)
    pairs = [(int(r), int(c)) for r, c in zip(rows, cols, strict=True) if cost[r, c] <= tolerance_s]
    used_e = {r for r, _ in pairs}
    used_d = {c for _, c in pairs}
    missed = [i for i in range(n_e) if i not in used_e]
    extras = [j for j in range(n_d) if j not in used_d]
    return sorted(pairs), missed, extras


def align(
    pattern: dict,
    detected_times: np.ndarray | list[float],
    *,
    bpm: float,
    countin_start_s: float,
    tolerance_s: float,
    latency_ms: float = 0.0,
    correct_offset: bool = True,
    fit_tempo: bool = True,
    max_offset_s: float = DEFAULT_MAX_OFFSET_S,
) -> Alignment:
    events = parse_events(pattern)
    n_count = count_in_beats(pattern)
    spb = seconds_per_beat(bpm)
    exp = expected_times(
        events, bpm=bpm, count_in=n_count, countin_start_s=countin_start_s, latency_ms=latency_ms
    )
    exp_t = np.array([e.time_s for e in exp])

    pattern_start = countin_start_s + n_count * spb + latency_ms / 1000.0
    pattern_end = pattern_start + length_beats(pattern) * spb
    win_lo = min(exp_t[0], pattern_start) - 0.5 * spb
    win_hi = max(exp_t[-1], pattern_end) + 0.5 * spb

    det_all = np.sort(np.asarray(detected_times, dtype=float))
    in_win = (det_all >= win_lo) & (det_all <= win_hi)
    det = det_all[in_win]
    ignored = det_all[~in_win].tolist()

    iois = np.diff(exp_t)
    min_ioi = float(iois.min()) if len(iois) else spb
    radius = max(tolerance_s, min(0.45 * min_ioi, max_offset_s + tolerance_s))
    pivot = float(exp_t[0])

    best = None
    scales = TEMPO_SCALES if (correct_offset and fit_tempo) else np.array([1.0])
    for scale in scales:
        grid = pivot + (exp_t - pivot) * scale
        off = estimate_global_offset(grid, det, radius, max_offset_s) if correct_offset else 0.0
        pairs, missed, extras = match(grid + off, det, tolerance_s)
        err = np.mean([abs(det[j] - grid[i] - off) for i, j in pairs]) if pairs else tolerance_s
        objective = len(pairs) - err / tolerance_s - SCALE_BIAS * abs(scale - 1.0)
        if best is None or objective > best[0] + 1e-9:
            best = (objective, float(scale), off, grid, pairs, missed, extras)
    _, scale, offset, grid, pairs, missed, extras = best

    matched = [
        MatchedPair(
            expected_index=i,
            detected_index=j,
            expected_s=round(float(exp_t[i]), 5),
            detected_s=round(float(det[j]), 5),
            error_ms=round(float((det[j] - offset - grid[i]) * 1000.0), 2),
        )
        for i, j in pairs
    ]
    return Alignment(
        expected=exp,
        detected_s=[round(float(t), 5) for t in det],
        matched=matched,
        missed=missed,
        extras=extras,
        ignored_s=[round(float(t), 5) for t in ignored],
        global_offset_ms=round(offset * 1000.0, 2),
        tempo_scale=round(scale, 3),
        window_s=(round(float(win_lo), 4), round(float(win_hi), 4)),
        pattern_span_s=(round(float(exp_t[0]), 4), round(float(exp_t[-1]), 4)),
    )
