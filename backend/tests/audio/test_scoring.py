"""Scenario suite from the spec (section 4.6) plus scoring unit tests."""

import pytest

from app.audio.align import align
from app.audio.scoring import (
    PRESETS,
    analyze_take,
    completion,
    evidence_factor,
    get_preset,
    pattern_accuracy,
    ramp,
    score_alignment,
    timing_accuracy,
)
from app.audio.synth import SynthOptions, render

from .conftest import EIGHT_HIT, SON_CLAVE_32, take

# ---------------------------------------------------------------- spec scenarios


@pytest.mark.parametrize("voice", [None, "low", "high", "shaker", "clap"])
@pytest.mark.parametrize("bpm", [70, 90, 120])
def test_perfect_performance_scores_at_least_95(voice, bpm):
    res, _ = take(
        EIGHT_HIT,
        bpm=bpm,
        voice=voice,
        jitter_ms=5,
        count_in_clicks=True,
        noise_level=0.003,
        rumble_level=0.02,
    )
    assert res.total >= 95
    assert not res.needs_review
    assert res.hits_matched == 8


def test_perfect_clave():
    res, _ = take(SON_CLAVE_32, bpm=100, jitter_ms=5)
    assert res.total >= 95


def test_consistent_late_60ms_scores_high_after_offset_correction():
    res, _ = take(EIGHT_HIT, preset="standard", global_offset_ms=60, jitter_ms=5)
    assert res.alignment["global_offset_ms"] == pytest.approx(60, abs=8)
    assert res.timing_accuracy >= 95
    assert res.total >= 95
    uncorrected, _ = take(
        EIGHT_HIT,
        preset="standard",
        global_offset_ms=60,
        jitter_ms=5,
        analyze_kwargs={"correct_offset": False},
    )
    assert uncorrected.timing_accuracy < res.timing_accuracy - 10


def test_two_missed_hits_of_eight():
    res, _ = take(EIGHT_HIT, miss_indices=[2, 5])
    assert res.hits_matched == 6
    assert len(res.alignment["missed"]) == 2
    assert res.pattern_accuracy == pytest.approx(100 * 12 / 14, abs=0.2)  # F1 = 85.7
    assert 85 <= res.total < 97


def test_extra_hits_are_penalised():
    clean, _ = take(EIGHT_HIT)
    res, _ = take(EIGHT_HIT, extra_count=3, seed=4)
    assert len(res.alignment["extras"]) == 3
    assert res.pattern_accuracy == pytest.approx(100 * 16 / 19, abs=0.2)  # F1 = 84.2
    assert res.total < clean.total


@pytest.mark.parametrize("noise", [0.08, 0.12, 0.25])
def test_heavy_noise_drops_confidence_and_flags_review(noise):
    res, _ = take(EIGHT_HIT, noise_level=noise, rumble_level=noise / 2)
    assert res.confidence < 0.5
    assert res.needs_review
    assert res.review_reasons


def test_tempo_speed_up_10_percent_drops_tempo_consistency():
    steady, _ = take(EIGHT_HIT, jitter_ms=5)
    fast, _ = take(EIGHT_HIT, jitter_ms=5, tempo_scale=1.1)
    assert fast.tempo_consistency <= 75
    assert steady.tempo_consistency - fast.tempo_consistency >= 20
    assert fast.alignment["tempo_scale"] == pytest.approx(0.91, abs=0.02)


def test_gradual_drift_is_detected():
    steady, _ = take(EIGHT_HIT, jitter_ms=5)
    drift, _ = take(EIGHT_HIT, jitter_ms=5, tempo_drift=0.2)
    assert drift.tempo_consistency < steady.tempo_consistency


def test_silence_scores_zero_and_needs_review():
    res, _ = take(EIGHT_HIT, hit_level=0.0)
    assert res.total == 0
    assert res.needs_review
    assert "No drum hits were heard." in res.review_reasons


# ---------------------------------------------------------------- additional behaviour


def test_calibrated_latency_is_compensated():
    # Recording made through a device with 150 ms round-trip latency, Challenge preset.
    s = render(EIGHT_HIT, SynthOptions(latency_ms=150, jitter_ms=3))
    kwargs = dict(sr=s.sr, bpm=90, countin_start_s=s.countin_start_s, preset="challenge")
    cal = analyze_take(s.audio, EIGHT_HIT, latency_ms=150, **kwargs)
    assert cal.total >= 95
    assert abs(cal.alignment["global_offset_ms"]) < 10
    uncal = analyze_take(s.audio, EIGHT_HIT, latency_ms=0, correct_offset=False, **kwargs)
    assert uncal.total < 50


def test_stricter_presets_lower_timing_for_sloppy_takes():
    long_pattern = {
        "count_in_beats": 4,
        "length_beats": 8,
        "events": [{"beat": b * 0.5, "voice": "low"} for b in range(16)],
    }
    scores = {}
    for preset in ("gentle", "standard", "challenge"):
        vals = [
            take(long_pattern, preset=preset, jitter_ms=50, seed=s)[0].timing_accuracy
            for s in range(3)
        ]
        scores[preset] = sum(vals) / len(vals)
    assert scores["gentle"] > scores["standard"] > scores["challenge"]


def test_lone_hit_does_not_earn_timing_or_completion_credit():
    res, _ = take(EIGHT_HIT, miss_indices=[0, 1, 2, 3, 4, 5, 6])
    assert res.hits_matched == 1
    assert res.total < 25
    assert res.needs_review


def test_score_result_serialises():
    res, _ = take(EIGHT_HIT)
    d = res.to_dict()
    assert set(res.categories) == {
        "pattern_accuracy",
        "timing_accuracy",
        "tempo_consistency",
        "completion",
    }
    assert d["alignment"]["matched"][0]["expected_index"] == 0
    assert len(d["detected_onsets"]) == 8


def test_unknown_mode_raises():
    al = align(EIGHT_HIT, [], bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    with pytest.raises(ValueError):
        score_alignment(al, confidence=1.0, preset=get_preset(None), mode="karaoke")


# ---------------------------------------------------------------- unit tests


def test_ramp():
    assert ramp(0.05, 0.08, 0.2) == 1.0
    assert ramp(0.2, 0.08, 0.2) == 0.0
    assert ramp(0.14, 0.08, 0.2) == pytest.approx(0.5)


def test_pattern_accuracy_f1():
    assert pattern_accuracy(8, 0, 0) == 100
    assert pattern_accuracy(0, 8, 0) == 0
    assert pattern_accuracy(0, 0, 0) == 0
    assert pattern_accuracy(6, 2, 0) == pytest.approx(85.714, abs=0.01)


def test_timing_accuracy_uses_preset_windows():
    gentle = PRESETS["gentle"]
    assert timing_accuracy([0, 80, -80], gentle) == 100
    assert timing_accuracy([140], gentle) == pytest.approx(50)
    assert timing_accuracy([250], gentle) == 0
    assert timing_accuracy([], gentle) == 0
    assert PRESETS["standard"].perfect_ms == 50 and PRESETS["challenge"].max_ms == 80


def test_evidence_factor():
    assert evidence_factor(4, 8) == 1.0
    assert evidence_factor(1, 8) == 0.25
    assert evidence_factor(0, 0) == 0.0


def test_completion_when_team_stops_early():
    spb = 60 / 90
    start = 0.5 + 4 * spb
    det = [start + e["beat"] * spb for e in EIGHT_HIT["events"][:4]]
    al = align(EIGHT_HIT, det, bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    assert completion(al) == pytest.approx(100 * 2.5 / 6.5, abs=0.5)


def test_custom_weights():
    al = align(EIGHT_HIT, [], bpm=90, countin_start_s=0.5, tolerance_s=0.2)
    res = score_alignment(
        al,
        confidence=0.0,
        preset=get_preset("gentle"),
        weights={"pattern": 1, "timing": 0, "tempo": 0, "completion": 0},
    )
    assert res.total == 0
