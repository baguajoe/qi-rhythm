import numpy as np
import pytest

from app.audio.calibration import (
    estimate_latency,
    latency_from_recording,
    measure_noise_floor,
    suggest_threshold,
)
from app.audio.onset import TARGET_SR
from app.audio.synth import SynthOptions, render, voice_sample


def test_noise_floor_of_quiet_room():
    rng = np.random.default_rng(0)
    y = (rng.standard_normal(TARGET_SR * 5) * 0.003).astype(np.float32)  # ~ -50 dBFS
    assert measure_noise_floor(y, sr=TARGET_SR) == pytest.approx(-50.5, abs=1.5)
    assert measure_noise_floor(np.zeros(TARGET_SR, dtype=np.float32), sr=TARGET_SR) == -120.0


def test_estimate_latency_median_of_taps():
    clicks = np.arange(8) * 0.6 + 1.0
    rng = np.random.default_rng(1)
    taps = clicks + 0.12 + rng.normal(0, 0.01, 8)
    est = estimate_latency(clicks, taps)
    assert est.latency_ms == pytest.approx(120, abs=8)
    assert est.taps_used == 8 and est.reliable


def test_estimate_latency_unreliable_with_few_taps():
    est = estimate_latency([1.0, 2.0, 3.0, 4.0], [1.1])
    assert not est.reliable
    assert estimate_latency([1.0], []).taps_used == 0


def test_latency_from_synthetic_recording():
    eight_clicks = {
        "count_in_beats": 0,
        "length_beats": 8,
        "events": [{"beat": b, "voice": "low"} for b in range(8)],
    }
    s = render(eight_clicks, SynthOptions(bpm=100, latency_ms=95, jitter_ms=8, seed=2))
    spb = 0.6
    click_times = [s.countin_start_s + b * spb for b in range(8)]
    est = latency_from_recording(s.audio, click_times, sr=s.sr)
    assert est.latency_ms == pytest.approx(95, abs=12)
    assert est.reliable


def _soft_loud_clip(soft=0.05, loud=0.8, noise=0.002):
    sr = 44100
    rng = np.random.default_rng(0)
    y = rng.standard_normal(sr * 3) * noise
    hit = voice_sample("low", sr, rng)
    y[int(0.8 * sr) : int(0.8 * sr) + len(hit)] += soft * hit
    y[int(1.8 * sr) : int(1.8 * sr) + len(hit)] += loud * hit
    return y.astype(np.float32), sr


def test_suggest_threshold_soft_and_loud():
    y, sr = _soft_loud_clip()
    sug = suggest_threshold(y, noise_floor_db=-54.0, sr=sr)
    assert sug.ok
    assert 0.03 <= sug.onset_threshold <= 0.3
    assert sug.loud_level_db > sug.soft_level_db


def test_suggest_threshold_warns_when_soft_hit_is_near_noise():
    y, sr = _soft_loud_clip(soft=0.01, noise=0.01)
    sug = suggest_threshold(y, noise_floor_db=-40.0, sr=sr)
    assert not sug.ok


def test_suggest_threshold_needs_two_hits():
    rng = np.random.default_rng(0)
    y = (rng.standard_normal(TARGET_SR * 2) * 0.002).astype(np.float32)
    sug = suggest_threshold(y, noise_floor_db=-54.0, sr=TARGET_SR)
    assert not sug.ok and sug.onset_threshold == 0.07
