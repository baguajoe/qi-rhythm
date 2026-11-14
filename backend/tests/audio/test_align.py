import numpy as np
import pytest

from app.audio.align import align, estimate_global_offset, expected_times, match
from app.audio.patterns import count_in_beats, length_beats, parse_events

from .conftest import EIGHT_HIT


def test_expected_times_include_countin_and_latency():
    evs = parse_events(EIGHT_HIT)
    exp = expected_times(evs, bpm=120, count_in=4, countin_start_s=0.3, latency_ms=50)
    assert exp[0].time_s == pytest.approx(0.3 + 2.0 + 0.05)
    assert exp[-1].time_s == pytest.approx(0.3 + 2.0 + 0.05 + 6.5 * 0.5)


def test_match_is_one_to_one_and_respects_tolerance():
    exp = np.array([1.0, 2.0, 3.0])
    det = np.array([1.02, 1.05, 2.5, 3.01])
    pairs, missed, extras = match(exp, det, 0.1)
    assert pairs == [(0, 0), (2, 3)]
    assert missed == [1]
    assert sorted(extras) == [1, 2]


def test_match_handles_empty_inputs():
    assert match(np.array([1.0]), np.array([]), 0.1) == ([], [0], [])
    assert match(np.array([]), np.array([1.0]), 0.1) == ([], [], [0])


def test_global_offset_is_median_and_clamped():
    exp = np.arange(8, dtype=float)
    assert estimate_global_offset(exp, exp + 0.06, 0.3, 0.2) == pytest.approx(0.06)
    assert estimate_global_offset(exp, exp + 0.28, 0.3, 0.2) == pytest.approx(0.2)
    # one stray hit is not enough evidence
    assert estimate_global_offset(exp, np.array([3.1]), 0.3, 0.2) == 0.0


def _times(pattern, bpm, start=0.5, delta=0.0):
    spb = 60 / bpm
    return [start + (count_in_beats(pattern) + e["beat"]) * spb + delta for e in pattern["events"]]


def test_align_removes_consistent_lateness():
    det = _times(EIGHT_HIT, 90, delta=0.06)
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.13)
    assert al.global_offset_ms == pytest.approx(60, abs=1)
    assert len(al.matched) == 8
    assert all(abs(m.error_ms) < 1 for m in al.matched)


def test_align_without_offset_correction_keeps_error():
    det = _times(EIGHT_HIT, 90, delta=0.06)
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.13, correct_offset=False)
    assert al.global_offset_ms == 0
    assert all(m.error_ms == pytest.approx(60, abs=1) for m in al.matched)


def test_count_in_bleed_and_trailing_noise_are_ignored():
    spb = 60 / 90
    clicks = [0.5 + k * spb for k in range(4)]
    tail = [0.5 + (4 + length_beats(EIGHT_HIT) + 2) * spb]
    det = clicks + _times(EIGHT_HIT, 90) + tail
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    assert len(al.matched) == 8 and al.extras == []
    assert len(al.ignored_s) == 5


def test_align_fits_uniform_tempo_change():
    spb = 60 / 90
    start = 0.5 + 4 * spb
    det = [start + e["beat"] * spb / 1.1 for e in EIGHT_HIT["events"]]
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    assert al.tempo_scale == pytest.approx(1 / 1.1, abs=0.01)
    assert [m.expected_index for m in al.matched] == list(range(8))


def test_tempo_fit_prefers_unity_for_on_tempo_takes():
    rng = np.random.default_rng(0)
    det = np.array(_times(EIGHT_HIT, 90)) + rng.normal(0, 0.02, 8)
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    assert al.tempo_scale == 1.0


def test_parse_events_validates():
    with pytest.raises(ValueError):
        parse_events({"events": []})
    with pytest.raises(ValueError):
        parse_events({"events": [{"beat": 0, "voice": "kazoo"}]})
    with pytest.raises(ValueError):
        parse_events({"events": [{"beat": -1}]})
    assert length_beats({"events": [{"beat": 5.5}]}) == 8.0
