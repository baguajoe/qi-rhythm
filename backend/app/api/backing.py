"""Backing tracks: admins upload loops; any instructor in the org can play them and measure bleed.

Bleed-measurement audio ("Measure music level") is analysed in memory and never stored.
"""

from flask import Blueprint, Response, abort, jsonify, request

from ..extensions import db
from ..models import BackingTrack, CalibrationProfile, ClassSession, Instructor, Rhythm
from ..services import backing as svc
from ..services.storage import get_storage
from .util import get_owned, instructor_required, json_body

bp = Blueprint("backing", __name__)


def _admin(me: Instructor) -> None:
    if me.role != "admin":
        abort(403, "Only an admin can change backing music.")


def _rhythm(rhythm_id: int) -> Rhythm:
    r = db.session.get(Rhythm, rhythm_id)
    if r is None:
        abort(404, "That rhythm wasn't found.")
    return r


def _payload(track: BackingTrack) -> dict:
    bleed = svc.latest_bleed(track)
    return {
        **track.to_dict(),
        "warnings": svc.track_warnings(track, track.rhythm),
        "music_level": bleed.to_dict() if bleed else None,
    }


@bp.get("/backing-tracks")
@instructor_required
def list_tracks(me: Instructor):
    q = BackingTrack.query.filter_by(organization_id=me.organization_id)
    rid = request.args.get("rhythm_id")
    if rid:
        if not rid.isdigit():
            abort(400, "rhythm_id must be a number.")
        q = q.filter_by(rhythm_id=int(rid))
    rows = q.order_by(BackingTrack.rhythm_id, BackingTrack.version).all()
    return jsonify(tracks=[_payload(t) for t in rows])


@bp.post("/rhythms/<int:rhythm_id>/backing-tracks")
@instructor_required
def upload(me: Instructor, rhythm_id: int):
    _admin(me)
    rhythm = _rhythm(rhythm_id)
    track = svc.save_upload(
        me.organization_id, me.id, rhythm, request.form, request.files.get("audio")
    )
    return jsonify(track=_payload(track)), 201


@bp.patch("/backing-tracks/<int:track_id>")
@instructor_required
def update(me: Instructor, track_id: int):
    _admin(me)
    track = get_owned(BackingTrack, track_id, me)
    svc.update_metadata(track, json_body())
    return jsonify(track=_payload(track))


@bp.delete("/backing-tracks/<int:track_id>")
@instructor_required
def delete(me: Instructor, track_id: int):
    _admin(me)
    svc.delete_track(get_owned(BackingTrack, track_id, me))
    return jsonify(ok=True)


@bp.get("/backing-tracks/<int:track_id>/audio")
@instructor_required
def audio(me: Instructor, track_id: int):
    track = get_owned(BackingTrack, track_id, me)
    if not track.usable and me.role != "admin":
        abort(403, "This track needs its source and license notes before it can be played.")
    data = get_storage().get(track.storage_key)
    return Response(
        data,
        mimetype="audio/wav",
        headers={"Cache-Control": "private, max-age=3600", "Content-Length": str(len(data))},
    )


def _form_float(name: str, label: str, lo: float, hi: float) -> float:
    try:
        v = float(request.form.get(name, ""))
    except ValueError:
        abort(400, f"{label} is missing.")
    if not lo <= v <= hi:
        abort(400, f"{label} doesn't look right.")
    return v


@bp.post("/backing-tracks/<int:track_id>/bleed")
@instructor_required
def measure(me: Instructor, track_id: int):
    """'Measure music level': the groove-only track recorded alone through the room speaker."""
    track = get_owned(BackingTrack, track_id, me)
    if track.version != "bed":
        abort(400, "Measure the music level with the groove-only track.")
    if not track.usable:
        abort(400, "Add the source and license notes before using this track.")
    f = request.files.get("audio")
    data = f.read() if f is not None else b""
    if len(data) < 1000:
        abort(400, "The recording was too short. Please try again.")
    bpm = _form_float("bpm", "The tempo", 20, 400)
    music_start_s = _form_float("music_start_s", "Music timing information", -1.0, 30.0)
    volume = _form_float("music_volume", "The music volume", 0.01, 1.0)

    session_id = request.form.get("session_id")
    calibration = None
    if session_id and session_id.isdigit():
        sess = get_owned(ClassSession, int(session_id), me)
        calibration = sess.calibration
    else:
        session_id = None
    if calibration is None:
        calibration = (
            CalibrationProfile.query.filter_by(organization_id=me.organization_id)
            .order_by(CalibrationProfile.created_at.desc(), CalibrationProfile.id.desc())
            .first()
        )
    latency = calibration.latency_offset_ms if calibration else 0.0
    row, prof = svc.measure_and_save(
        track,
        data,
        bpm=bpm,
        music_start_s=music_start_s,
        music_volume=volume,
        latency_ms=latency,
        session_id=int(session_id) if session_id else None,
    )
    tone, message = svc.bleed_message(prof)
    return jsonify(music_level=row.to_dict(), tone=tone, message=message), 201
