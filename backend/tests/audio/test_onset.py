import io

import numpy as np
import pytest

from app.audio.onset import (
    TARGET_SR,
    OnsetParams,
    analyze_clip,
    detect_onsets,
    estimate_noise_floor_db,
    load_audio,
)
from app.audio.synth import SynthOptions, render, write_wav

from .conftest import EIGHT_HIT


def _errors_ms(detected, truth):
    detected = np.asarray(detected)
    return np.array([(detected[np.argmin(np.abs(detected - t))] - t) * 1000 for t in truth])


@pytest.mark.parametrize("voice", ["low", "high", "shaker", "clap"])
def test_detects_every_strike_precisely(voice):
    s = render(EIGHT_HIT, SynthOptions(voice=voice))
    res = analyze_clip(s.audio, sr=s.sr)
    assert len(res.onsets) == 8
    assert np.max(np.abs(_errors_ms(res.times, s.hit_times))) < 5.0
    assert res.confidence > 0.8


def test_detection_with_room_noise_and_rumble():
    s = render(EIGHT_HIT, SynthOptions(noise_level=0.01, rumble_level=0.05, level_jitter=0.3))
    res = analyze_clip(s.audio, sr=s.sr)
    assert len(res.onsets) == 8
    assert np.max(np.abs(_errors_ms(res.times, s.hit_times))) < 5.0


def test_min_gap_merges_flams():
    # Two strikes 30 ms apart should register as one with the default 70 ms gap.
    pattern = {"count_in_beats": 0, "length_beats": 4, "events": [{"beat": 0, "voice": "low"}]}
    s = render(pattern, SynthOptions(bpm=60))
    y = s.audio.copy()
    shift = int(0.03 * s.sr)
    y[shift:] += 0.6 * s.audio[:-shift]
    res = analyze_clip(y, sr=s.sr)
    assert len(res.onsets) == 1


def test_silence_returns_no_onsets_and_zero_confidence():
    res = detect_onsets(np.zeros(TARGET_SR * 3, dtype=np.float32))
    assert res.onsets == [] and res.confidence == 0.0


def test_quiet_noise_only_is_gated():
    rng = np.random.default_rng(0)
    y = (rng.standard_normal(TARGET_SR * 4) * 0.003).astype(np.float32)
    res = detect_onsets(y)
    assert len(res.onsets) <= 1
    assert res.confidence < 0.5


def test_calibrated_noise_floor_gates_soft_hits():
    s = render(EIGHT_HIT, SynthOptions(hit_level=0.02))
    loose = analyze_clip(s.audio, sr=s.sr)
    strict = analyze_clip(s.audio, sr=s.sr, params=OnsetParams(noise_floor_db=-30.0))
    assert len(loose.onsets) == 8
    assert len(strict.onsets) == 0


def test_heavy_noise_lowers_confidence():
    clean = render(EIGHT_HIT, SynthOptions())
    noisy = render(EIGHT_HIT, SynthOptions(noise_level=0.12, rumble_level=0.06))
    c_clean = analyze_clip(clean.audio, sr=clean.sr).confidence
    c_noisy = analyze_clip(noisy.audio, sr=noisy.sr).confidence
    assert c_noisy < 0.5 < c_clean


def test_load_audio_resamples_and_downmixes(tmp_path):
    s = render(EIGHT_HIT, SynthOptions(sr=48000))
    path = tmp_path / "x.wav"
    write_wav(path, s.audio, s.sr)
    y, sr = load_audio(str(path))
    assert sr == TARGET_SR
    assert abs(len(y) / sr - len(s.audio) / 48000) < 0.01
    # bytes input and stereo arrays also work
    y2, _ = load_audio(path.read_bytes())
    assert len(y2) == len(y)
    stereo = np.stack([s.audio, s.audio], axis=1)
    y3, _ = load_audio(stereo, sr=48000)
    assert len(y3) == len(y)
    with pytest.raises(ValueError):
        load_audio(s.audio)
    assert io  # keep import used for clarity of supported types


def test_noise_floor_estimate():
    rng = np.random.default_rng(1)
    y = (rng.standard_normal(TARGET_SR * 3) * 0.01).astype(np.float32)  # -40 dBFS RMS
    assert abs(estimate_noise_floor_db(y, percentile=50) - (-40.0)) < 1.5
