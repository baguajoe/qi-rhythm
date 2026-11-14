from flask import Blueprint, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from ..extensions import db
from ..models import CalibrationProfile, ClassSession, Instructor, Rhythm, Round, Score, Team
from ..models.base import utcnow
from ..services import game
from .util import get_owned, instructor_required, json_body

bp = Blueprint("sessions", __name__)

MAX_UPLOAD_SECONDS_SLACK = 10.0


def _session_payload(sess: ClassSession) -> dict:
    return {
        "session": sess.to_dict(),
        "rounds": [game.round_payload(r) for r in sess.rounds],
        "scoreboard": game.scoreboard(sess),
        "calibration": sess.calibration.to_dict() if sess.calibration else None,
    }


def _owned_round(rnd_id: int, me: Instructor) -> Round:
    rnd = db.session.get(Round, rnd_id)
    if rnd is None or rnd.session.organization_id != me.organization_id:
        abort(404, "Not found.")
    return rnd


# ---------------------------------------------------------------- sessions


@bp.post("/sessions")
@instructor_required
def start_session(me: Instructor):
    data = request.get_json(silent=True) or {}
    settings = game.validate_settings(data.get("settings") or {})
    profile_id = data.get("calibration_profile_id")
    if profile_id is not None:
        profile = get_owned(CalibrationProfile, int(profile_id), me)
    else:
        profile = (
            CalibrationProfile.query.filter_by(organization_id=me.organization_id)
            .order_by(CalibrationProfile.created_at.desc(), CalibrationProfile.id.desc())
            .first()
        )
    sess = ClassSession(
        organization_id=me.organization_id,
        instructor_id=me.id,
        settings={**game.DEFAULT_SESSION_SETTINGS, **settings},
        calibration_profile_id=profile.id if profile else None,
    )
    db.session.add(sess)
    db.session.commit()
    return jsonify(_session_payload(sess)), 201


@bp.get("/sessions/<int:session_id>")
@instructor_required
def get_session(me: Instructor, session_id: int):
    return jsonify(_session_payload(get_owned(ClassSession, session_id, me)))


@bp.patch("/sessions/<int:session_id>")
@instructor_required
def update_session(me: Instructor, session_id: int):
    sess = get_owned(ClassSession, session_id, me)
    data = json_body()
    if "settings" in data:
        patch = game.validate_settings(data["settings"] or {})
        sess.settings = {**game.session_settings(sess), **patch}
    if "calibration_profile_id" in data:
        pid = data["calibration_profile_id"]
        sess.calibration_profile_id = (
            get_owned(CalibrationProfile, int(pid), me).id if pid else None
        )
    db.session.commit()
    game.broadcast(sess.id, "session:settings", {"settings": game.session_settings(sess)})
    game.broadcast(sess.id, "scoreboard:updated", game.scoreboard(sess))
    return jsonify(_session_payload(sess))


@bp.post("/sessions/<int:session_id>/end")
@instructor_required
def end_session(me: Instructor, session_id: int):
    sess = get_owned(ClassSession, session_id, me)
    if sess.ended_at is None:
        sess.ended_at = utcnow()
        db.session.commit()
        game.broadcast(sess.id, "session:ended", game.scoreboard(sess))
    return jsonify(_session_payload(sess))


# ---------------------------------------------------------------- rounds


@bp.post("/sessions/<int:session_id>/rounds")
@instructor_required
def create_round(me: Instructor, session_id: int):
    sess = get_owned(ClassSession, session_id, me)
    data = json_body()
    rhythm = db.session.get(Rhythm, int(data.get("rhythm_id") or 0))
    if rhythm is None:
        abort(400, "Please choose a rhythm.")
    team = get_owned(Team, int(data.get("team_id") or 0), me)
    mult = data.get("tempo_multiplier")
    rnd = game.create_round(
        sess,
        rhythm,
        team,
        data.get("game_mode", "rhythm_recall"),
        float(mult) if mult is not None else None,
    )
    return jsonify(round=game.round_payload(rnd)), 201


@bp.patch("/rounds/<int:round_id>")
@instructor_required
def control_round(me: Instructor, round_id: int):
    rnd = _owned_round(round_id, me)
    status = json_body().get("status")
    return jsonify(round=game.round_payload(game.set_status(rnd, status)))


@bp.post("/rounds/<int:round_id>/recording")
@instructor_required
def upload_recording(me: Instructor, round_id: int):
    rnd = _owned_round(round_id, me)
    f = request.files.get("audio")
    if f is None:
        abort(400, "No recording was received. Please try the turn again.")
    audio = f.read()
    if len(audio) < 1000:
        abort(400, "The recording was too short. Please try the turn again.")
    try:
        countin_start_s = float(request.form.get("countin_start_s", ""))
    except ValueError:
        abort(400, "Recording timing information is missing.")
    if not -1.0 <= countin_start_s <= MAX_UPLOAD_SECONDS_SLACK:
        abort(400, "Recording timing information doesn't look right.")
    music = None
    if request.form.get("backing_track_id"):
        try:
            music = {
                "backing_track_id": int(request.form["backing_track_id"]),
                "music_start_s": float(request.form.get("music_start_s", "")),
                "music_volume": float(request.form.get("music_volume", "")),
            }
        except ValueError:
            abort(400, "Music timing information is missing.")
        if not -1.0 <= music["music_start_s"] <= MAX_UPLOAD_SECONDS_SLACK:
            abort(400, "Music timing information doesn't look right.")
        if not 0.0 < music["music_volume"] <= 1.0:
            abort(400, "The music volume doesn't look right.")
    try:
        score = game.process_recording(rnd, audio, countin_start_s, music)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - unreadable audio etc.; round is marked failed
        abort(422, "We couldn't read that recording. Please try the turn again.")
    return jsonify(round=game.round_payload(rnd), score=score.to_dict()), 201


@bp.get("/rounds/<int:round_id>/score")
@instructor_required
def get_score(me: Instructor, round_id: int):
    rnd = _owned_round(round_id, me)
    if rnd.score is None:
        abort(404, "This turn hasn't been scored yet.")
    return jsonify(score=rnd.score.to_dict(), round=game.round_payload(rnd))


# ---------------------------------------------------------------- scores


def _owned_score(score_id: int, me: Instructor) -> Score:
    sc = db.session.get(Score, score_id)
    if sc is None or sc.round.session.organization_id != me.organization_id:
        abort(404, "Not found.")
    return sc


@bp.post("/scores/<int:score_id>/override")
@instructor_required
def override(me: Instructor, score_id: int):
    sc = _owned_score(score_id, me)
    data = json_body()
    game.override_score(sc, data, data.get("reason"), me.id)
    return jsonify(score=sc.to_dict(), round=game.round_payload(sc.round))


@bp.post("/scores/<int:score_id>/confirm")
@instructor_required
def confirm(me: Instructor, score_id: int):
    sc = game.confirm_score(_owned_score(score_id, me))
    return jsonify(score=sc.to_dict())


# ---------------------------------------------------------------- privacy


@bp.post("/recordings/purge")
@instructor_required
def purge(me: Instructor):
    """'Delete recordings now' — removes every stored recording for this organization."""
    n = game.purge_recordings(org_id=me.organization_id)
    return jsonify(deleted=n)


@bp.patch("/organization")
@instructor_required
def update_org(me: Instructor):
    if not me.is_admin:
        abort(403, "Only an admin can change organization settings.")
    data = json_body()
    if "recording_retention_days" in data:
        try:
            days = int(data["recording_retention_days"])
        except (TypeError, ValueError):
            abort(400, "Retention must be a whole number of days.")
        if not 0 <= days <= 90:
            abort(400, "Keep recordings for 0 to 90 days.")
        me.organization.recording_retention_days = days
    db.session.commit()
    return jsonify(organization=me.organization.to_dict())
