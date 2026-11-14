import numpy as np
import soundfile as sf

from app.audio.synth import SynthOptions, render

from .conftest import EIGHT_HIT


def test_render_is_deterministic_for_a_seed():
    a = render(EIGHT_HIT, SynthOptions(jitter_ms=20, noise_level=0.01, seed=3))
    b = render(EIGHT_HIT, SynthOptions(jitter_ms=20, noise_level=0.01, seed=3))
    assert np.array_equal(a.audio, b.audio)
    assert a.hit_times == b.hit_times


def test_hit_times_follow_tempo_and_count_in():
    s = render(EIGHT_HIT, SynthOptions(bpm=120, lead_in_s=0.25))
    spb = 0.5
    expected = [0.25 + 4 * spb + e["beat"] * spb for e in EIGHT_HIT["events"]]
    assert np.allclose(s.hit_times, expected, atol=1e-9)


def test_missed_and_extra_hits():
    s = render(EIGHT_HIT, SynthOptions(miss_count=2, extra_count=3, seed=1))
    assert len(s.missed_indices) == 2
    assert len(s.hit_times) == 6
    assert len(s.extra_times) == 3


def test_offset_latency_and_tempo_scale():
    base = render(EIGHT_HIT, SynthOptions())
    late = render(EIGHT_HIT, SynthOptions(global_offset_ms=60, latency_ms=40))
    assert np.allclose(np.array(late.hit_times) - base.hit_times, 0.1)
    fast = render(EIGHT_HIT, SynthOptions(tempo_scale=1.1))
    span_base = base.hit_times[-1] - base.hit_times[0]
    span_fast = fast.hit_times[-1] - fast.hit_times[0]
    assert abs(span_fast - span_base / 1.1) < 1e-9


def test_write_wav_roundtrip(tmp_path):
    s = render(EIGHT_HIT, SynthOptions(sr=48000))
    path = tmp_path / "take.wav"
    s.write(path)
    info = sf.info(str(path))
    assert info.samplerate == 48000 and info.channels == 1 and info.subtype == "PCM_16"
    data, _ = sf.read(str(path))
    assert np.max(np.abs(data)) <= 1.0


def test_audio_is_clipped_to_full_scale():
    s = render(EIGHT_HIT, SynthOptions(hit_level=3.0))
    assert np.max(np.abs(s.audio)) <= 1.0
