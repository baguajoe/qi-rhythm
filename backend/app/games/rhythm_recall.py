"""Rhythm Recall: hear a pattern, then the team plays it back from memory."""

from __future__ import annotations

import io

import soundfile as sf
from flask import current_app

from ..audio.bleed import BleedProfile, bleed_params
from ..audio.onset import OnsetParams
from ..audio.patterns import count_in_beats
from ..audio.scoring import ScoreResult, analyze_take
from .base import GameMode, GameModeKey, register

SLACK_BEATS = 4  # one bar of slack after the pattern (spec 4.1)
UNMEASURED_MUSIC = (
    "Music was playing but its level hasn't been measured, so some music sounds may have "
    "counted as hits. Press \u201cMeasure music level\u201d before the next turn."
)


def music_for(round_) -> dict | None:
    """Usable backing tracks for this round's rhythm, unless music is switched off."""
    from ..services.backing import usable_tracks
    from ..services.game import session_settings

    sess = round_.session
    if sess is None or not session_settings(sess).get("music_on", True):
        return None
    tracks = usable_tracks(sess.organization_id, round_.rhythm_id)
    if not tracks:
        return None
    return {v: (tracks[v].playback_dict() if v in tracks else None) for v in ("full", "bed")}


class RhythmRecall(GameMode):
    key = GameModeKey.RHYTHM_RECALL
    label = "Rhythm Recall"

    def setup(self, round_, settings: dict) -> dict:
        return {"tolerance_preset": settings.get("tolerance_preset", "gentle")}

    def reference(self, round_) -> dict:
        r = round_.rhythm
        return {
            "rhythm_id": r.id,
            "title": r.title,
            "pattern": r.engine_pattern,
            "bpm": round_.tempo_bpm_used,
            "length_beats": r.length_beats,
            "music": music_for(round_),
        }

    def capture(self, round_) -> dict:
        p = round_.rhythm.engine_pattern
        n_count = count_in_beats(p)
        spb = 60.0 / round_.tempo_bpm_used
        return {
            "count_in_beats": n_count,
            "record_seconds": round((n_count + round_.rhythm.length_beats + SLACK_BEATS) * spb, 3),
        }

    def analyze(self, round_, audio: bytes, meta: dict, calibration) -> ScoreResult:
        params = OnsetParams()
        latency = 0.0
        if calibration is not None:
            params.threshold = calibration.onset_threshold
            params.noise_floor_db = calibration.noise_floor_db
            latency = calibration.latency_offset_ms
        round_.latency_ms_used = latency
        music_unmeasured = False
        track = round_.backing_track
        if track is not None and round_.music_start_s is not None:
            from ..services.backing import latest_bleed

            measured = latest_bleed(track, round_.session.organization_id)
            if measured is None:
                music_unmeasured = True
            else:
                params = bleed_params(
                    BleedProfile.from_dict(measured.profile),
                    params,
                    bpm=round_.tempo_bpm_used,
                    bed_start_s=round_.music_start_s,
                    duration_s=sf.info(io.BytesIO(audio)).duration,
                    latency_ms=latency,
                    music_volume=round_.music_volume_used,
                )
        result = analyze_take(
            audio,
            round_.rhythm.engine_pattern,
            bpm=round_.tempo_bpm_used,
            countin_start_s=meta["countin_start_s"],
            latency_ms=latency,
            preset=round_.tolerance_preset,
            onset_params=params,
            mode=self.key.value,
            weights=current_app.config["SCORE_WEIGHTS"],
        )
        if music_unmeasured and result.hits_detected:
            result.review_reasons.append(UNMEASURED_MUSIC)
            result.needs_review = True
        return result

    def score(self, round_, analysis: ScoreResult) -> dict:
        return {
            "pattern_accuracy": analysis.pattern_accuracy,
            "timing_accuracy": analysis.timing_accuracy,
            "tempo_consistency": analysis.tempo_consistency,
            "completion": analysis.completion,
            "total": analysis.total,
            "confidence": analysis.confidence,
            "needs_review": analysis.needs_review,
            "review_reasons": analysis.review_reasons,
            "detected_onsets": analysis.detected_onsets,
            "matched_pairs": analysis.alignment,
        }


register(RhythmRecall())
