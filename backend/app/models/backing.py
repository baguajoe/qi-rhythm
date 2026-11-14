"""Backing tracks: an organization's own loops (e.g. exported from Cubase) attached to a rhythm.

"full" = the groove with the pattern audible (played while the team listens);
"bed"  = the groove only (played under the team's turn; the mic hears it, see audio/bleed.py).
A track can be used in a class only once its source and license notes are filled in.

Two levels: tracks with ``organization_id IS NULL`` form the platform-wide Qi Rhythm Library
(owned by Eye Forge Studios, changed only by super-admins, available to every organization);
tracks with an organization are that organization's private loops and, per version, play
instead of the library's.
"""

from ..extensions import db
from .base import utcnow

TRACK_VERSIONS = ("full", "bed")
TRACK_SOURCES = ("original", "commissioned", "licensed")
LIBRARY_NAME = "Qi Rhythm Library"
LIBRARY_OWNER = "Eye Forge Studios"
LIBRARY_BADGE = "Qi Rhythm Original"


def beats_per_bar(time_signature: str) -> float:
    """Pulses per bar in the library's beat units (a dotted quarter in compound meters)."""
    try:
        num, den = (int(x) for x in (time_signature or "4/4").split("/"))
    except ValueError:
        return 4.0
    if den == 8 and num % 3 == 0 and num > 3:
        return float(num // 3)
    return float(num)


class BackingTrack(db.Model):
    __tablename__ = "backing_tracks"
    __table_args__ = (
        # One private track per (org, rhythm, version)...
        db.UniqueConstraint("organization_id", "rhythm_id", "version", name="uq_backing_version"),
        # ...and one library track per (rhythm, version) (NULLs are distinct in the constraint).
        db.Index(
            "uq_backing_library_version",
            "rhythm_id",
            "version",
            unique=True,
            postgresql_where=db.text("organization_id IS NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # NULL = Qi Rhythm Library (platform-wide)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=True, index=True)
    rhythm_id = db.Column(db.ForeignKey("rhythms.id"), nullable=False, index=True)
    version = db.Column(
        db.Enum(*TRACK_VERSIONS, name="track_version", native_enum=False), nullable=False
    )
    bpm = db.Column(db.Float, nullable=False)
    bars = db.Column(db.Integer, nullable=False)
    beats_per_bar = db.Column(db.Float, nullable=False, default=4.0)
    notes = db.Column(db.Text, nullable=False, default="")
    storage_key = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False, default="")
    sample_rate = db.Column(db.Integer, nullable=False)
    channels = db.Column(db.Integer, nullable=False)
    duration_s = db.Column(db.Float, nullable=False)
    source = db.Column(db.Enum(*TRACK_SOURCES, name="track_source", native_enum=False))
    license_notes = db.Column(db.Text, nullable=False, default="")
    uploaded_by = db.Column(db.ForeignKey("instructors.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    rhythm = db.relationship("Rhythm")

    @property
    def is_library(self) -> bool:
        return self.organization_id is None

    @property
    def loop_beats(self) -> float:
        return self.bars * self.beats_per_bar

    @property
    def expected_duration_s(self) -> float:
        return self.loop_beats * 60.0 / self.bpm

    @property
    def usable(self) -> bool:
        return bool(self.source) and bool((self.license_notes or "").strip())

    def to_dict(self):
        return {
            "id": self.id,
            "rhythm_id": self.rhythm_id,
            "version": self.version,
            "scope": "library" if self.is_library else "organization",
            "badge": LIBRARY_BADGE if self.is_library else None,
            "bpm": self.bpm,
            "bars": self.bars,
            "beats_per_bar": self.beats_per_bar,
            "loop_beats": self.loop_beats,
            "notes": self.notes,
            "original_filename": self.original_filename,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_s": round(self.duration_s, 3),
            "expected_duration_s": round(self.expected_duration_s, 3),
            "loop_seconds": round(self.expected_duration_s, 5),
            "rev": self.updated_at.isoformat() if self.updated_at else None,
            "source": self.source,
            "license_notes": self.license_notes,
            "usable": self.usable,
            "audio_path": f"/api/backing-tracks/{self.id}/audio",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def playback_dict(self):
        """What the class page needs to play it in time."""
        return {
            "id": self.id,
            "version": self.version,
            "scope": "library" if self.is_library else "organization",
            "badge": LIBRARY_BADGE if self.is_library else None,
            "bpm": self.bpm,
            "loop_beats": self.loop_beats,
            "loop_seconds": round(self.expected_duration_s, 5),
            "audio_path": f"/api/backing-tracks/{self.id}/audio",
            "rev": self.updated_at.isoformat() if self.updated_at else None,
        }


class MusicBleedProfile(db.Model):
    """'Measure music level' result: how the bed track sounds at the room mic (no audio kept).

    Always belongs to the organization that measured it (rooms differ), even for library tracks.
    """

    __tablename__ = "music_bleed_profiles"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    backing_track_id = db.Column(
        db.ForeignKey("backing_tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = db.Column(db.ForeignKey("sessions.id", ondelete="SET NULL"))
    profile = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        p = self.profile or {}
        return {
            "id": self.id,
            "backing_track_id": self.backing_track_id,
            "music_level_db": p.get("floor_db"),
            "music_volume": p.get("music_volume"),
            "transients_per_loop": len(p.get("transients", [])),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
