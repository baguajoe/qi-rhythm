"""Backing tracks, in two levels:

- the Qi Rhythm Library (``organization_id IS NULL``): owned by Eye Forge Studios, available to
  every organization, changed only by super-admins;
- an organization's private tracks: changed by that organization's admins; per version they play
  instead of the library's.

Any instructor can list and play the tracks visible to their organization and measure the music
level. Bleed-measurement audio ("Measure music level") is analysed in memory and never stored.
"""

from flask import Blueprint, Response, abort, jsonify, request

from ..extensions import db
from ..models import BackingTrack, CalibrationProfile, ClassSession, Instructor, Rhythm
from ..models.backing import LIBRARY_NAME, LIBRARY_OWNER
from ..services import backing as svc
from ..services.storage import get_storage
from .util import get_owned, instructor_required, json_body

bp = Blueprint("backing", __name__)


def _rhythm(rhythm_id: int) -> Rhythm:
    r = db.session.get(Rhythm, rhythm_id)
    if r is None:
        abort(404, "That rhythm wasn't found.")
    return r


def _visible(track_id: int, me: Instructor) -> BackingTrack:
    """A library track or one of this organization's own; 404 otherwise."""
    t = db.session.get(BackingTrack, track_id)
    if t is None or t.organization_id not in (None, me.organization_id):
        abort(404, "Not found.")
    return t


def _can_edit(track: BackingTrack, me: Instructor) -> bool:
    return me.is_superadmin if track.is_library else me.is_admin


def _require_edit(track: BackingTrack, me: Instructor) -> None:
    if track.is_library and not me.is_superadmin:
        abort(403, f"Only the {LIBRARY_OWNER} team can change {LIBRARY_NAME} tracks.")
    if not me.is_admin:
        abort(403, "Only an admin can change backing music.")


def _payload(track: BackingTrack, me: Instructor, in_use_ids: set[int] | None = None) -> dict:
    bleed = svc.latest_bleed(track, me.organization_id)
    if in_use_ids is None:
        in_use_ids = {t.id for t in svc.usable_tracks(me.organization_id, track.rhythm_id).values()}
    return {
        **track.to_dict(),
        "warnings": svc.track_warnings(track, track.rhythm),
        "music_level": bleed.to_dict() if bleed else None,
        "in_use": track.id in in_use_ids,  # what plays in this organization's classes
        "can_edit": _can_edit(track, me),
    }


@bp.get("/backing-tracks")
@instructor_required
def list_tracks(me: Instructor):
    rid = request.args.get("rhythm_id")
    if rid and not rid.isdigit():
        abort(400, "rhythm_id must be a number.")
    rows = (
        svc.visible_tracks(me.organization_id, int(rid) if rid else None)
        .order_by(
            BackingTrack.rhythm_id,
            BackingTrack.organization_id.is_(None).desc(),  # library first
            BackingTrack.version,
        )
        .all()
    )
    in_use = {
        t.id
        for r in {t.rhythm_id for t in rows}
        for t in svc.usable_tracks(me.organization_id, r).values()
    }
    return jsonify(
        tracks=[_payload(t, me, in_use) for t in rows],
        library={"name": LIBRARY_NAME, "owner": LIBRARY_OWNER, "can_edit": me.is_superadmin},
    )


@bp.post("/rhythms/<int:rhythm_id>/backing-tracks")
@instructor_required
def upload(me: Instructor, rhythm_id: int):
    """Upload a loop. ``scope=library`` adds it to the Qi Rhythm Library (super-admins only)."""
    scope = request.form.get("scope", "organization")
    if scope not in ("organization", "library"):
        abort(400, "Choose the Qi Rhythm Library or your organization.")
    if scope == "library" and not me.is_superadmin:
        abort(403, f"Only the {LIBRARY_OWNER} team can add tracks to the {LIBRARY_NAME}.")
    if not me.is_admin:
        abort(403, "Only an admin can change backing music.")
    rhythm = _rhythm(rhythm_id)
    org_id = None if scope == "library" else me.organization_id
    track = svc.save_upload(org_id, me.id, rhythm, request.form, request.files.get("audio"))
    return jsonify(track=_payload(track, me)), 201


@bp.patch("/backing-tracks/<int:track_id>")
@instructor_required
def update(me: Instructor, track_id: int):
    track = _visible(track_id, me)
    _require_edit(track, me)
    svc.update_metadata(track, json_body())
    return jsonify(track=_payload(track, me))


@bp.delete("/backing-tracks/<int:track_id>")
@instructor_required
def delete(me: Instructor, track_id: int):
    track = _visible(track_id, me)
    _require_edit(track, me)
    svc.delete_track(track)
    return jsonify(ok=True)


@bp.get("/backing-tracks/<int:track_id>/audio")
@instructor_required
def audio(me: Instructor, track_id: int):
    track = _visible(track_id, me)
    if not track.usable and not _can_edit(track, me):
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
    track = _visible(track_id, me)
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
        me.organization_id,
        data,
        bpm=bpm,
        music_start_s=music_start_s,
        music_volume=volume,
        latency_ms=latency,
        session_id=int(session_id) if session_id else None,
    )
    tone, message = svc.bleed_message(prof)
    return jsonify(music_level=row.to_dict(), tone=tone, message=message), 201
