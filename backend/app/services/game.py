"""Round lifecycle: create -> reference -> record -> analyze -> score -> confirm/override."""

from __future__ import annotations

import uuid
from datetime import timedelta

from flask import abort, current_app

from ..extensions import db
from ..games import get_mode
from ..models import ClassSession, Rhythm, Round, Score, Team
from ..models.base import utcnow
from ..models.session import CATEGORY_FIELDS, DEFAULT_SESSION_SETTINGS
from ..sockets.broadcast import broadcast
from ..sockets.state import update_live
from .storage import get_storage

TOLERANCE_PRESETS = ("gentle", "standard", "challenge")
# Statuses the instructor can move a round into directly.
CONTROL_TRANSITIONS = {
    "playing_reference": {"pending", "playing_reference", "recording", "failed"},
    "recording": {"pending", "playing_reference", "recording", "failed"},
    "pending": {"pending", "playing_reference", "recording", "failed"},  # Stop
}
# The server marks a round "recording" just before the count-in starts, so the Display shows
# "Get ready" (round:countin); the instructor's client sends round:recording after the count-in.
STATUS_EVENTS = {
    "playing_reference": "round:reference_playing",
    "recording": "round:countin",
    "pending": "round:stopped",
}


def session_settings(sess: ClassSession) -> dict:
    return {**DEFAULT_SESSION_SETTINGS, **(sess.settings or {})}


def validate_settings(patch: dict) -> dict:
    out = {}
    for key, value in patch.items():
        if key not in DEFAULT_SESSION_SETTINGS:
            abort(400, f"Unknown setting {key!r}.")
        default = DEFAULT_SESSION_SETTINGS[key]
        if key == "tolerance_preset":
            if value not in TOLERANCE_PRESETS:
                abort(400, "Choose Gentle, Standard, or Challenge.")
        elif isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, float | int):
            try:
                value = float(value)
            except (TypeError, ValueError):
                abort(400, f"{key} must be a number.")
            if key == "tempo_multiplier" and not 0.5 <= value <= 1.2:
                abort(400, "Speed must be between 50% and 120%.")
            if key in ("volume", "music_volume") and not 0 <= value <= 1:
                abort(400, "Volume must be between 0 and 1.")
            if key == "speech_rate" and not 0.5 <= value <= 1.5:
                abort(400, "Speech rate must be between 0.5 and 1.5.")
        out[key] = value
    return out


def round_payload(rnd: Round) -> dict:
    mode = get_mode(rnd.game_mode)
    return {
        **rnd.to_dict(),
        "team": rnd.team.to_dict(include_participants=False),
        "rhythm": {"id": rnd.rhythm.id, "title": rnd.rhythm.title},
        "reference": mode.reference(rnd),
        "capture": mode.capture(rnd),
    }


def create_round(
    sess: ClassSession,
    rhythm: Rhythm,
    team: Team,
    game_mode: str,
    tempo_multiplier: float | None = None,
) -> Round:
    if sess.ended_at is not None:
        abort(409, "This class has ended. Start a new class to keep playing.")
    settings = session_settings(sess)
    mult = tempo_multiplier if tempo_multiplier is not None else settings["tempo_multiplier"]
    if not 0.5 <= mult <= 1.2:
        abort(400, "Speed must be between 50% and 120%.")
    try:
        mode = get_mode(game_mode)
    except ValueError:
        abort(400, "That game isn't available yet.")
    rnd = Round(
        session_id=sess.id,
        game_mode=mode.key,
        rhythm_id=rhythm.id,
        team_id=team.id,
        tempo_bpm_used=round(rhythm.bpm * mult, 2),
        tolerance_preset=settings["tolerance_preset"],
        status="pending",
    )
    rnd.rhythm, rnd.team = rhythm, team
    mode.setup(rnd, settings)
    db.session.add(rnd)
    db.session.commit()
    broadcast(sess.id, "round:started", round_payload(rnd))
    return rnd


def set_status(rnd: Round, status: str) -> Round:
    if status not in CONTROL_TRANSITIONS or rnd.status not in CONTROL_TRANSITIONS[status]:
        abort(409, "That step isn't possible right now.")
    rnd.status = status
    db.session.commit()
    update_live(
        rnd.session_id,
        phase={"playing_reference": "reference", "recording": "countin", "pending": "idle"}[status],
    )
    broadcast(rnd.session_id, STATUS_EVENTS[status], round_payload(rnd))
    return rnd


def recompute_team_points(team: Team) -> None:
    scores = Score.query.join(Round).filter(Round.team_id == team.id).all()
    team.total_points = round(sum(s.effective_total for s in scores), 1)


def process_recording(
    rnd: Round, audio: bytes, countin_start_s: float, music: dict | None = None
) -> Score:
    """``music`` = {backing_track_id, music_start_s, music_volume} when a bed track played."""
    if rnd.status in ("scored", "overridden"):
        abort(409, "This turn already has a score. Start a new turn to play again.")
    if rnd.session.ended_at is not None:
        abort(409, "This class has ended.")
    track = None
    if music:
        from ..models import BackingTrack

        track = db.session.get(BackingTrack, int(music["backing_track_id"]))
        if (
            track is None
            or track.organization_id not in (None, rnd.session.organization_id)
            or track.rhythm_id != rnd.rhythm_id
            or track.version != "bed"
            or not track.usable
        ):
            abort(400, "That backing track can't be used for this turn.")
    rnd.backing_track = track
    rnd.music_start_s = music["music_start_s"] if track else None
    rnd.music_volume_used = music["music_volume"] if track else None
    rnd.status = "analyzing"
    rnd.countin_start_s = countin_start_s
    db.session.commit()
    update_live(rnd.session_id, phase="analyzing", count=None)
    broadcast(rnd.session_id, "round:analyzing", {"round_id": rnd.id, "team_id": rnd.team_id})

    key = (
        f"recordings/org-{rnd.session.organization_id}/session-{rnd.session_id}/"
        f"round-{rnd.id}-{uuid.uuid4().hex[:8]}.wav"
    )
    get_storage().put(key, audio, "audio/wav")
    rnd.recording_key = key

    mode = get_mode(rnd.game_mode)
    try:
        analysis = mode.analyze(
            rnd, audio, {"countin_start_s": countin_start_s}, rnd.session.calibration
        )
    except Exception as exc:  # noqa: BLE001 - surface a friendly error, keep the round recoverable
        current_app.logger.exception("analysis failed for round %s", rnd.id)
        rnd.status = "failed"
        rnd.error_message = "We couldn't read that recording. Please try the turn again."
        db.session.commit()
        update_live(rnd.session_id, phase="idle")
        broadcast(rnd.session_id, "round:failed", {"round_id": rnd.id})
        raise exc
    fields = mode.score(rnd, analysis)
    score = Score(round_id=rnd.id, **fields)
    db.session.add(score)
    rnd.status = "scored"
    rnd.error_message = None
    db.session.flush()
    recompute_team_points(rnd.team)
    db.session.commit()
    update_live(rnd.session_id, phase="scored")
    broadcast(rnd.session_id, "round:scored", round_payload(rnd))
    broadcast(rnd.session_id, "scoreboard:updated", scoreboard(rnd.session))
    return score


def override_score(score: Score, values: dict, reason: str | None, instructor_id: int) -> Score:
    clean = {}
    for key in (*CATEGORY_FIELDS, "total"):
        if key in values and values[key] is not None:
            try:
                v = float(values[key])
            except (TypeError, ValueError):
                abort(400, "Scores must be numbers from 0 to 100.")
            if not 0 <= v <= 100:
                abort(400, "Scores must be numbers from 0 to 100.")
            clean[key] = round(v, 1)
    if not clean:
        abort(400, "Change at least one score.")
    if "total" not in clean:
        weights = current_app.config["SCORE_WEIGHTS"]
        merged = {**score.machine, **clean}
        name = {
            "pattern": "pattern_accuracy",
            "timing": "timing_accuracy",
            "tempo": "tempo_consistency",
            "completion": "completion",
        }
        clean["total"] = round(
            sum(merged[name[k]] * w for k, w in weights.items()) / sum(weights.values()), 1
        )
    score.is_override = True
    score.override_values = clean
    score.override_reason = (reason or "").strip()[:255] or None
    score.overridden_by = instructor_id
    score.confirmed_at = utcnow()
    rnd = score.round
    rnd.status = "overridden"
    recompute_team_points(rnd.team)
    db.session.commit()
    broadcast(rnd.session_id, "round:overridden", round_payload(rnd))
    broadcast(rnd.session_id, "scoreboard:updated", scoreboard(rnd.session))
    return score


def confirm_score(score: Score) -> Score:
    score.confirmed_at = utcnow()
    db.session.commit()
    return score


def scoreboard(sess: ClassSession) -> dict:
    """Running team totals for this class (effective scores, overrides applied)."""
    rows: dict[int, dict] = {}
    for rnd in sess.rounds:
        t = rnd.team
        row = rows.setdefault(
            t.id,
            {"team": t.to_dict(include_participants=False), "points": 0.0, "turns": 0, "best": 0.0},
        )
        if rnd.score is not None:
            total = rnd.score.effective_total
            row["points"] = round(row["points"] + total, 1)
            row["turns"] += 1
            row["best"] = max(row["best"], total)
    ranked = sorted(rows.values(), key=lambda r: (-r["points"], r["team"]["name"]))
    return {
        "session_id": sess.id,
        "teams": ranked,
        "cooperative": bool(session_settings(sess).get("cooperative_mode")),
        "group_points": round(sum(r["points"] for r in ranked), 1),
    }


def purge_recordings(org_id: int | None = None, older_than_days: int | None = None) -> int:
    """Delete stored recordings. With ``older_than_days`` only those past retention."""
    from ..models import Organization

    q = Round.query.join(ClassSession).filter(
        Round.recording_key.isnot(None), Round.recording_deleted_at.is_(None)
    )
    if org_id is not None:
        q = q.filter(ClassSession.organization_id == org_id)
    storage = get_storage()
    now = utcnow()
    n = 0
    for rnd in q.all():
        if older_than_days is None:
            limit = None
        else:
            org = db.session.get(Organization, rnd.session.organization_id)
            limit = org.recording_retention_days if older_than_days < 0 else older_than_days
        if limit is not None and rnd.created_at > now - timedelta(days=limit):
            continue
        try:
            storage.delete(rnd.recording_key)
        except Exception:  # noqa: BLE001
            current_app.logger.exception("could not delete %s", rnd.recording_key)
            continue
        rnd.recording_deleted_at = now
        n += 1
    db.session.commit()
    return n
