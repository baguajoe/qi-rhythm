"""Score a performance against the reference pattern.

Categories (0-100 each):
- pattern_accuracy: F1 of matched strikes (penalises both misses and extras)
- timing_accuracy: per matched strike, full credit inside the preset's "perfect" window, linear
  fall-off to zero at the preset's max window
- tempo_consistency: inter-onset intervals of matched strikes vs the reference IOIs
- completion: how much of the pattern's span the team played through

Timing, tempo and completion are scaled by an *evidence factor*
``min(1, matched / ceil(expected / 2))`` so one lucky hit in a near-silent take cannot earn full
timing/completion credit. Takes with at least half the strikes matched are unaffected.

Scoring takes a game ``mode`` so future modes (Phase 2+) can reuse the onset/alignment engine
with their own weights or category rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .align import Alignment, align
from .onset import OnsetParams, OnsetResult, analyze_clip

# ---------------------------------------------------------------- presets & profiles


@dataclass(frozen=True)
class TolerancePreset:
    key: str
    label: str
    perfect_ms: float
    max_ms: float


PRESETS: dict[str, TolerancePreset] = {
    "gentle": TolerancePreset("gentle", "Gentle", 80, 200),
    "standard": TolerancePreset("standard", "Standard", 50, 130),
    "challenge": TolerancePreset("challenge", "Challenge", 30, 80),
}
DEFAULT_PRESET = "gentle"

DEFAULT_WEIGHTS = {"pattern": 40, "timing": 30, "tempo": 15, "completion": 15}

# Per-mode scoring weights. TODO(phase-2): add finish_the_beat, music_memory, call_and_response.
MODE_WEIGHTS: dict[str, dict[str, float]] = {"rhythm_recall": DEFAULT_WEIGHTS}

CONFIDENCE_REVIEW_THRESHOLD = 0.5
HIT_RATIO_RANGE = (0.5, 2.0)  # detected/expected outside this => "wildly off"

# Tempo-consistency ramps (relative IOI error)
TEMPO_OVERALL_FULL, TEMPO_OVERALL_ZERO = 0.03, 0.15
TEMPO_STEADY_FULL, TEMPO_STEADY_ZERO = 0.06, 0.25


def get_preset(key: str | None) -> TolerancePreset:
    return PRESETS[key or DEFAULT_PRESET]


def ramp(x: float, full: float, zero: float) -> float:
    """1.0 at or below ``full``, 0.0 at or above ``zero``, linear in between."""
    if x <= full:
        return 1.0
    if x >= zero:
        return 0.0
    return 1.0 - (x - full) / (zero - full)


# ---------------------------------------------------------------- result


@dataclass
class ScoreResult:
    mode: str
    preset: str
    pattern_accuracy: float
    timing_accuracy: float
    tempo_consistency: float
    completion: float
    total: float
    confidence: float
    needs_review: bool
    review_reasons: list[str]
    hits_expected: int
    hits_detected: int
    hits_matched: int
    alignment: dict = field(default_factory=dict)
    detected_onsets: list[dict] = field(default_factory=list)

    @property
    def categories(self) -> dict[str, float]:
        return {
            "pattern_accuracy": self.pattern_accuracy,
            "timing_accuracy": self.timing_accuracy,
            "tempo_consistency": self.tempo_consistency,
            "completion": self.completion,
        }

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- category scores


def evidence_factor(n_matched: int, n_expected: int) -> float:
    if n_expected == 0:
        return 0.0
    return min(1.0, n_matched / max(1, int(np.ceil(n_expected / 2))))


def pattern_accuracy(n_matched: int, n_missed: int, n_extra: int) -> float:
    denom = 2 * n_matched + n_missed + n_extra
    return 100.0 * 2 * n_matched / denom if denom else 0.0


def timing_accuracy(errors_ms: list[float], preset: TolerancePreset) -> float:
    if not errors_ms:
        return 0.0
    credits = [ramp(abs(e), preset.perfect_ms, preset.max_ms) for e in errors_ms]
    return 100.0 * float(np.mean(credits))


def tempo_consistency(al: Alignment) -> float:
    """Compare performed vs reference inter-onset intervals of consecutive matched strikes.

    Combines the overall tempo ratio (rushing/dragging) with steadiness (spread of individual
    IOI ratios), so a single slightly early hit does not dominate.
    """
    if len(al.matched) < 2:
        return 0.0
    ref = np.diff([m.expected_s for m in al.matched])
    perf = np.diff([m.detected_s for m in al.matched])
    ok = ref > 1e-6
    ref, perf = ref[ok], perf[ok]
    if len(ref) == 0:
        return 0.0
    overall = float(perf.sum() / ref.sum())
    steadiness = float(np.median(np.abs(perf / ref - overall)))
    score = 0.6 * ramp(abs(overall - 1.0), TEMPO_OVERALL_FULL, TEMPO_OVERALL_ZERO)
    score += 0.4 * ramp(steadiness, TEMPO_STEADY_FULL, TEMPO_STEADY_ZERO)
    return 100.0 * score


def completion(al: Alignment) -> float:
    """Share of the pattern's span (first to last expected strike) the team played through."""
    if not al.matched:
        return 0.0
    first, last = al.pattern_span_s
    if last - first <= 1e-6:
        return 100.0
    reached = max(m.expected_s for m in al.matched)
    return 100.0 * float(np.clip((reached - first) / (last - first), 0.0, 1.0))


# ---------------------------------------------------------------- main entry points


def score_alignment(
    al: Alignment,
    *,
    confidence: float,
    preset: TolerancePreset,
    mode: str = "rhythm_recall",
    weights: dict[str, float] | None = None,
    detected_onsets: list[dict] | None = None,
) -> ScoreResult:
    if mode not in MODE_WEIGHTS:
        raise ValueError(f"unsupported game mode {mode!r}")
    w = weights or MODE_WEIGHTS[mode]

    n_exp = len(al.expected)
    n_det = len(al.detected_s)
    ev = evidence_factor(len(al.matched), n_exp)
    cats = {
        "pattern": pattern_accuracy(len(al.matched), len(al.missed), len(al.extras)),
        "timing": ev * timing_accuracy([m.error_ms for m in al.matched], preset),
        "tempo": ev * tempo_consistency(al),
        "completion": ev * completion(al),
    }
    total = sum(cats[k] * w[k] for k in cats) / sum(w.values())

    reasons = []
    if n_det == 0:
        reasons.append("No drum hits were heard.")
    elif confidence < CONFIDENCE_REVIEW_THRESHOLD:
        reasons.append("The recording was noisy or quiet, so hits were hard to hear.")
    if n_det and not (HIT_RATIO_RANGE[0] <= n_det / n_exp <= HIT_RATIO_RANGE[1]):
        reasons.append(
            f"Heard {n_det} hits but the pattern has {n_exp}, which is a big difference."
        )

    return ScoreResult(
        mode=mode,
        preset=preset.key,
        pattern_accuracy=round(cats["pattern"], 1),
        timing_accuracy=round(cats["timing"], 1),
        tempo_consistency=round(cats["tempo"], 1),
        completion=round(cats["completion"], 1),
        total=round(total, 1),
        confidence=round(float(confidence), 3),
        needs_review=bool(reasons),
        review_reasons=reasons,
        hits_expected=n_exp,
        hits_detected=n_det,
        hits_matched=len(al.matched),
        alignment=al.to_dict(),
        detected_onsets=detected_onsets or [],
    )


def analyze_take(
    source,
    pattern: dict,
    *,
    bpm: float,
    countin_start_s: float,
    sr: int | None = None,
    latency_ms: float = 0.0,
    preset: str | None = None,
    onset_params: OnsetParams | None = None,
    mode: str = "rhythm_recall",
    weights: dict[str, float] | None = None,
    correct_offset: bool = True,
    fit_tempo: bool = True,
) -> ScoreResult:
    """Full pipeline: audio -> onsets -> alignment -> score."""
    tol = get_preset(preset)
    onsets: OnsetResult = analyze_clip(source, sr=sr, params=onset_params)
    al = align(
        pattern,
        onsets.times,
        bpm=bpm,
        countin_start_s=countin_start_s,
        tolerance_s=tol.max_ms / 1000.0,
        latency_ms=latency_ms,
        correct_offset=correct_offset,
        fit_tempo=fit_tempo,
    )
    return score_alignment(
        al,
        confidence=onsets.confidence,
        preset=tol,
        mode=mode,
        weights=weights,
        detected_onsets=[
            {"time_s": o.time_s, "strength": round(o.strength, 3), "level_db": round(o.level_db, 1)}
            for o in onsets.onsets
        ],
    )


def warmup() -> None:
    """Trigger librosa/numba JIT compilation so the first real analysis is fast."""
    rng = np.random.default_rng(0)
    y = (rng.standard_normal(22050) * 0.01).astype(np.float32)
    y[5000:5200] += 0.5
    analyze_clip(y, sr=22050)
