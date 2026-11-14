"""Calibration helpers: noise floor, device latency, and onset sensitivity.

Run once per room/device by the calibration wizard; results are saved as a CalibrationProfile.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .onset import (
    OnsetParams,
    detect_onsets,
    estimate_noise_floor_db,
    frame_rms_db,
    highpass,
    load_audio,
)

DEFAULT_THRESHOLD = 0.07


@dataclass
class LatencyEstimate:
    latency_ms: float
    taps_used: int
    spread_ms: float  # median absolute deviation; large = unreliable tapping
    reliable: bool


def measure_noise_floor(source, sr: int | None = None) -> float:
    """Typical background level of a quiet-room recording, in dBFS (median short-term RMS)."""
    y, sr = load_audio(source, sr)
    y = highpass(y, sr, 70.0)
    if not np.any(y):
        return -120.0
    return round(float(np.median(frame_rms_db(y))), 1)


def estimate_latency(
    click_times_s: list[float] | np.ndarray,
    tap_times_s: list[float] | np.ndarray,
    max_lag_s: float = 0.4,
) -> LatencyEstimate:
    """Median offset between scheduled clicks and the instructor's drum taps.

    Both lists are in the recording's time base. Each click is paired with its nearest tap within
    ``max_lag_s``; the median difference is the device round-trip latency (plus a small human
    reaction component, which is the same during real play and therefore desirable).
    """
    clicks = np.asarray(click_times_s, dtype=float)
    taps = np.asarray(tap_times_s, dtype=float)
    diffs = []
    for c in clicks:
        if len(taps) == 0:
            break
        j = int(np.argmin(np.abs(taps - c)))
        if abs(taps[j] - c) <= max_lag_s:
            diffs.append(taps[j] - c)
    if not diffs:
        return LatencyEstimate(0.0, 0, 0.0, False)
    d = np.array(diffs)
    med = float(np.median(d))
    mad = float(np.median(np.abs(d - med)))
    reliable = len(d) >= max(4, len(clicks) // 2) and mad * 1000 <= 40
    return LatencyEstimate(round(med * 1000, 1), len(d), round(mad * 1000, 1), reliable)


def latency_from_recording(
    source, click_times_s: list[float], sr: int | None = None
) -> LatencyEstimate:
    y, sr = load_audio(source, sr)
    res = detect_onsets(y, sr, OnsetParams())
    return estimate_latency(click_times_s, res.times)


@dataclass
class SensitivitySuggestion:
    onset_threshold: float
    soft_level_db: float | None
    loud_level_db: float | None
    noise_floor_db: float
    ok: bool
    message: str


def suggest_threshold(
    source, noise_floor_db: float, sr: int | None = None
) -> SensitivitySuggestion:
    """From a clip with one soft and one loud hit, suggest a peak-pick threshold.

    The onset envelope is normalised to the loudest hit, so the threshold must sit comfortably
    below the soft hit's relative strength.
    """
    y, sr = load_audio(source, sr)
    res = detect_onsets(
        y, sr, OnsetParams(threshold=0.02, noise_floor_db=noise_floor_db, gate_margin_db=3.0)
    )
    if len(res.onsets) < 2:
        return SensitivitySuggestion(
            DEFAULT_THRESHOLD,
            None,
            None,
            noise_floor_db,
            False,
            "We heard fewer than two hits. Try again with one soft hit and one loud hit.",
        )
    by_level = sorted(res.onsets, key=lambda o: o.level_db)
    soft, loud = by_level[0], by_level[-1]
    thr = float(np.clip(0.5 * soft.strength, 0.03, 0.3))
    ok = soft.level_db - noise_floor_db >= 10
    msg = (
        "Sounds good. Soft hits are clearly heard."
        if ok
        else "Soft hits are close to the room noise. Ask the group to play a little louder."
    )
    return SensitivitySuggestion(
        round(thr, 3), round(soft.level_db, 1), round(loud.level_db, 1), noise_floor_db, ok, msg
    )


def clip_noise_floor(source, sr: int | None = None) -> float:
    y, sr = load_audio(source, sr)
    return round(estimate_noise_floor_db(highpass(y, sr, 70.0)), 1)
