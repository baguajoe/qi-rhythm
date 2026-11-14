import pytest

from app.audio.scoring import analyze_take, warmup
from app.audio.synth import SynthOptions, render

# 8 strikes over two 4/4 bars, mixed voices (spacing >= half a beat)
EIGHT_HIT = {
    "subdivision": 4,
    "count_in_beats": 4,
    "length_beats": 8,
    "events": [
        {"beat": 0.0, "voice": "low", "accent": True},
        {"beat": 1.0, "voice": "high"},
        {"beat": 1.5, "voice": "high"},
        {"beat": 2.5, "voice": "low"},
        {"beat": 4.0, "voice": "low", "accent": True},
        {"beat": 5.0, "voice": "high"},
        {"beat": 5.5, "voice": "high"},
        {"beat": 6.5, "voice": "low"},
    ],
}

# Son clave 3-2 over two bars (beat units)
SON_CLAVE_32 = {
    "subdivision": 4,
    "count_in_beats": 4,
    "length_beats": 8,
    "events": [{"beat": b, "voice": "clap"} for b in (0.0, 1.5, 3.0, 5.0, 6.0)],
}


@pytest.fixture(scope="session", autouse=True)
def _jit_warmup():
    warmup()


@pytest.fixture
def eight_hit():
    return EIGHT_HIT


def take(pattern, bpm=90.0, preset="gentle", latency_ms=0.0, analyze_kwargs=None, **synth_kw):
    """Render a synthetic take and analyse it; returns (ScoreResult, SynthResult)."""
    s = render(pattern, SynthOptions(bpm=bpm, **synth_kw))
    res = analyze_take(
        s.audio,
        pattern,
        sr=s.sr,
        bpm=bpm,
        countin_start_s=s.countin_start_s,
        preset=preset,
        latency_ms=latency_ms,
        **(analyze_kwargs or {}),
    )
    return res, s
