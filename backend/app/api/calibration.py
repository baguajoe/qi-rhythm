"""Calibration wizard endpoints. Calibration audio is analysed in memory and never stored."""

import json

from flask import Blueprint, abort, jsonify, request

from ..audio import calibration as cal
from ..extensions import db
from ..models import CalibrationProfile, Instructor
from .util import instructor_required, json_body, require_str

bp = Blueprint("calibration", __name__)


def _uploaded_audio() -> bytes:
    f = request.files.get("audio")
    if f is None:
        abort(400, "No recording was received. Please try again.")
    data = f.read()
    if len(data) < 1000:
        abort(400, "The recording was too short. Please try again.")
    return data


def _float_field(name: str, default=None):
    raw = request.form.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        abort(400, f"Invalid value for {name}.")


@bp.get("")
@instructor_required
def list_profiles(me: Instructor):
    rows = (
        CalibrationProfile.query.filter_by(organization_id=me.organization_id)
        .order_by(CalibrationProfile.created_at.desc(), CalibrationProfile.id.desc())
        .all()
    )
    return jsonify(profiles=[p.to_dict() for p in rows])


@bp.post("")
@instructor_required
def save_profile(me: Instructor):
    data = json_body()
    label = require_str(data, "device_label", "a name for this room or device", 120)
    try:
        latency = float(data.get("latency_offset_ms", 0.0))
        threshold = float(data.get("onset_threshold", 0.07))
        floor = data.get("noise_floor_db")
        floor = None if floor is None else float(floor)
    except (TypeError, ValueError):
        abort(400, "Calibration values must be numbers.")
    if not -100 <= latency <= 600:
        abort(400, "That latency doesn't look right. Please run the tap test again.")
    if not 0.01 <= threshold <= 0.5:
        abort(400, "Sensitivity is out of range.")
    p = CalibrationProfile(
        organization_id=me.organization_id,
        device_label=label,
        latency_offset_ms=latency,
        noise_floor_db=floor,
        onset_threshold=threshold,
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(profile=p.to_dict()), 201


@bp.post("/analyze/noise")
@instructor_required
def analyze_noise(me: Instructor):
    floor = cal.measure_noise_floor(_uploaded_audio())
    if floor > -30:
        msg = "The room is quite noisy. Turning off fans or music will help the app hear drums."
    elif floor > -45:
        msg = "The room is a little noisy, but that's okay."
    else:
        msg = "The room is nice and quiet."
    return jsonify(noise_floor_db=floor, message=msg)


@bp.post("/analyze/latency")
@instructor_required
def analyze_latency(me: Instructor):
    audio = _uploaded_audio()
    try:
        clicks = json.loads(request.form.get("click_times", "[]"))
        clicks = [float(c) for c in clicks]
    except (ValueError, TypeError):
        abort(400, "Click times are missing.")
    if len(clicks) < 4:
        abort(400, "Click times are missing.")
    est = cal.latency_from_recording(audio, clicks)
    msg = (
        "Got it. The timing is measured."
        if est.reliable
        else "We couldn't hear enough steady taps. Please try again and tap along with each click."
    )
    return jsonify(
        latency_offset_ms=est.latency_ms,
        taps_used=est.taps_used,
        spread_ms=est.spread_ms,
        reliable=est.reliable,
        message=msg,
    )


@bp.post("/analyze/sensitivity")
@instructor_required
def analyze_sensitivity(me: Instructor):
    floor = _float_field("noise_floor_db", -60.0)
    sug = cal.suggest_threshold(_uploaded_audio(), noise_floor_db=floor)
    return jsonify(
        onset_threshold=sug.onset_threshold,
        soft_level_db=sug.soft_level_db,
        loud_level_db=sug.loud_level_db,
        ok=sug.ok,
        message=sug.message,
    )
