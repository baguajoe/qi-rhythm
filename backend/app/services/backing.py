"""Backing-track uploads, validation, and music-bleed measurement."""

from __future__ import annotations

import io
import uuid

import soundfile as sf
from flask import abort

from ..audio.bleed import BleedProfile, measure_bleed
from ..extensions import db
from ..models import BackingTrack, MusicBleedProfile, Rhythm
from ..models.backing import TRACK_SOURCES, TRACK_VERSIONS, beats_per_bar
from ..models.base import utcnow
from .storage import get_storage

ALLOWED_RATES = (44100, 48000)
# The loop length must match bars x BPM to within this, or the music drifts off the beat grid.
DURATION_TOLERANCE_S = 0.05
DURATION_TOLERANCE_FRAC = 0.01
MAX_BPM_DIFF_FRAC = 0.2  # warn when the loop is far from the rhythm's own tempo
MAX_NOTES = 2000
VERSION_LABELS = {"full": "Full (pattern audible)", "bed": "Groove only"}


def inspect_wav(data: bytes) -> dict:
    """Check that ``data`` is a WAV at 44.1 or 48 kHz; return its format details."""
    try:
        info = sf.info(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - soundfile raises various errors for non-audio
        abort(400, "That file isn't a WAV file we can read. Please export a WAV from Cubase.")
    if info.format not in ("WAV", "WAVEX"):
        abort(400, f"That file is {info.format}, not WAV. Please export a WAV file.")
    if info.samplerate not in ALLOWED_RATES:
        abort(
            400,
            f"That WAV is {info.samplerate / 1000:g} kHz. Please export at 44.1 kHz or 48 kHz.",
        )
    if info.frames <= 0:
        abort(400, "That WAV file is empty.")
    return {
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "duration_s": info.frames / info.samplerate,
        "subtype": info.subtype,
    }


def track_warnings(track: BackingTrack, rhythm: Rhythm) -> list[str]:
    """Plain-language checks shown after upload. Warnings don't block use."""
    out = []
    expected = track.expected_duration_s
    diff = track.duration_s - expected
    if abs(diff) > max(DURATION_TOLERANCE_S, DURATION_TOLERANCE_FRAC * expected):
        bars = f"{track.bars} bar{'s' if track.bars != 1 else ''}"
        out.append(
            f"The file is {track.duration_s:.2f} s long, but {bars} at {track.bpm:g} BPM "
            f"should be {expected:.2f} s ({'longer' if diff > 0 else 'shorter'} by "
            f"{abs(diff):.2f} s). Check the BPM and bars, or the export range in Cubase, "
            "or the music will drift away from the beat."
        )
    if abs(track.bpm - rhythm.bpm) > MAX_BPM_DIFF_FRAC * rhythm.bpm:
        out.append(
            f"This loop is {track.bpm:g} BPM but the rhythm is {rhythm.bpm:g} BPM. It will be "
            "sped up or slowed down to match, which can sound unnatural."
        )
    loop, length = track.loop_beats, rhythm.length_beats
    if loop > 0 and not (_is_multiple(length, loop) or _is_multiple(loop, length)):
        out.append(
            f"The loop is {loop:g} beats but the pattern is {length:g} beats, so the loop won't "
            "line up with the start of each pattern."
        )
    if not track.usable:
        out.append("Add the source and license notes before this track can be used in a class.")
    return out


def _is_multiple(a: float, b: float) -> bool:
    if b <= 0:
        return False
    q = a / b
    return abs(q - round(q)) < 1e-6 and round(q) >= 1


def _parse_metadata(form, rhythm: Rhythm, partial: bool = False) -> dict:
    out: dict = {}
    if "version" in form or not partial:
        version = form.get("version")
        if version not in TRACK_VERSIONS:
            abort(400, "Choose Full (pattern audible) or Groove only.")
        out["version"] = version
    if "bpm" in form or not partial:
        try:
            bpm = float(form.get("bpm", ""))
        except ValueError:
            abort(400, "Please enter the loop's BPM as a number.")
        if not 30 <= bpm <= 300:
            abort(400, "BPM must be between 30 and 300.")
        out["bpm"] = bpm
    if "bars" in form or not partial:
        try:
            bars = int(str(form.get("bars", "")).strip())
        except ValueError:
            abort(400, "Please enter the number of bars as a whole number.")
        if not 1 <= bars <= 64:
            abort(400, "Bars must be between 1 and 64.")
        out["bars"] = bars
    if "notes" in form:
        out["notes"] = str(form.get("notes") or "").strip()[:MAX_NOTES]
    if "source" in form:
        source = form.get("source") or None
        if source is not None and source not in TRACK_SOURCES:
            abort(400, "Source must be original, commissioned, or licensed.")
        out["source"] = source
    if "license_notes" in form:
        out["license_notes"] = str(form.get("license_notes") or "").strip()[:MAX_NOTES]
    return out


def save_upload(org_id: int, instructor_id: int, rhythm: Rhythm, form, file) -> BackingTrack:
    """Validate and store an uploaded WAV; replaces this org's track of the same version."""
    meta = _parse_metadata(form, rhythm)
    data = file.read() if file is not None else b""
    if not data:
        abort(400, "Please choose a WAV file to upload.")
    wav = inspect_wav(data)
    key = f"backing/org-{org_id}/rhythm-{rhythm.id}/{meta['version']}-{uuid.uuid4().hex[:10]}.wav"
    storage = get_storage()
    storage.put(key, data, "audio/wav")

    track = BackingTrack.query.filter_by(
        organization_id=org_id, rhythm_id=rhythm.id, version=meta["version"]
    ).one_or_none()
    old_key = track.storage_key if track else None
    if track is None:
        track = BackingTrack(organization_id=org_id, rhythm_id=rhythm.id, version=meta["version"])
        db.session.add(track)
    else:
        # A new recording invalidates earlier "Measure music level" results.
        MusicBleedProfile.query.filter_by(backing_track_id=track.id).delete()
    track.rhythm = rhythm
    track.bpm, track.bars = meta["bpm"], meta["bars"]
    track.beats_per_bar = beats_per_bar(rhythm.time_signature)
    track.notes = meta.get("notes", "")
    track.source = meta.get("source")
    track.license_notes = meta.get("license_notes", "")
    track.storage_key = key
    track.original_filename = (getattr(file, "filename", "") or "")[:255]
    track.sample_rate, track.channels = wav["sample_rate"], wav["channels"]
    track.duration_s = wav["duration_s"]
    track.uploaded_by = instructor_id
    track.updated_at = utcnow()
    db.session.commit()
    if old_key and old_key != key:
        try:
            storage.delete(old_key)
        except Exception:  # noqa: BLE001 - an orphaned file is harmless
            pass
    return track


def update_metadata(track: BackingTrack, data: dict) -> BackingTrack:
    meta = _parse_metadata(data, track.rhythm, partial=True)
    meta.pop("version", None)  # the file decides the version; upload again to change it
    for k, v in meta.items():
        setattr(track, k, v)
    track.updated_at = utcnow()
    db.session.commit()
    return track


def delete_track(track: BackingTrack) -> None:
    key = track.storage_key
    db.session.delete(track)
    db.session.commit()
    try:
        get_storage().delete(key)
    except Exception:  # noqa: BLE001
        pass


def usable_tracks(org_id: int, rhythm_id: int) -> dict[str, BackingTrack]:
    rows = BackingTrack.query.filter_by(organization_id=org_id, rhythm_id=rhythm_id).all()
    return {t.version: t for t in rows if t.usable}


def latest_bleed(track: BackingTrack) -> MusicBleedProfile | None:
    return (
        MusicBleedProfile.query.filter_by(backing_track_id=track.id)
        .order_by(MusicBleedProfile.created_at.desc(), MusicBleedProfile.id.desc())
        .first()
    )


def measure_and_save(
    track: BackingTrack,
    audio: bytes,
    *,
    bpm: float,
    music_start_s: float,
    music_volume: float,
    latency_ms: float,
    session_id: int | None,
) -> tuple[MusicBleedProfile, BleedProfile]:
    try:
        prof = measure_bleed(
            audio,
            bpm=bpm,
            bed_start_s=music_start_s,
            loop_beats=track.loop_beats,
            latency_ms=latency_ms,
            music_volume=music_volume,
        )
    except Exception:  # noqa: BLE001
        abort(400, "We couldn't read that recording. Please try again.")
    row = MusicBleedProfile(
        organization_id=track.organization_id,
        backing_track_id=track.id,
        session_id=session_id,
        profile=prof.to_dict(),
    )
    db.session.add(row)
    db.session.commit()
    return row, prof


def bleed_message(prof: BleedProfile) -> tuple[str, str]:
    """(tone, message) describing a measurement in plain language."""
    if prof.floor_db < -75 and not prof.transients:
        return (
            "warning",
            "We couldn't hear the music. Check that the speaker is on and the music volume "
            "is up, then measure again.",
        )
    if prof.floor_db > -20:
        return (
            "warning",
            "The music is very loud at the microphone. Turning the music down a little will "
            "help the app hear the drums.",
        )
    n = len(prof.transients)
    return (
        "success",
        f"Music level measured. The app now knows the music's own beats ({n} per loop) and "
        "won't count them as your team's playing.",
    )
