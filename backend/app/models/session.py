from ..extensions import db
from ..games.base import GameModeKey
from .base import utcnow

ROUND_STATUSES = (
    "pending",
    "playing_reference",
    "recording",
    "analyzing",
    "scored",
    "overridden",
    "failed",
)

DEFAULT_SESSION_SETTINGS = {
    "tolerance_preset": "gentle",
    "volume": 0.8,  # the pattern (synthesized drums) and count-in clicks
    "music_volume": 0.6,  # backing tracks
    "music_on": True,
    "tempo_multiplier": 1.0,
    "high_contrast": False,
    "spoken_instructions": False,
    "speech_rate": 0.9,
    "cooperative_mode": False,
    "auto_advance": False,
}


class ClassSession(db.Model):
    """One class meeting run by an instructor ("Session" in the product language)."""

    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    instructor_id = db.Column(db.ForeignKey("instructors.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at = db.Column(db.DateTime(timezone=True))
    settings = db.Column(db.JSON, nullable=False, default=lambda: dict(DEFAULT_SESSION_SETTINGS))
    calibration_profile_id = db.Column(db.ForeignKey("calibration_profiles.id"))

    rounds = db.relationship("Round", back_populates="session", order_by="Round.id")
    calibration = db.relationship("CalibrationProfile")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "instructor_id": self.instructor_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "settings": {**DEFAULT_SESSION_SETTINGS, **(self.settings or {})},
            "calibration_profile_id": self.calibration_profile_id,
        }


class Round(db.Model):
    __tablename__ = "rounds"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.ForeignKey("sessions.id"), nullable=False, index=True)
    game_mode = db.Column(
        db.Enum(
            GameModeKey,
            name="game_mode",
            native_enum=False,
            length=40,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=GameModeKey.RHYTHM_RECALL,
    )
    rhythm_id = db.Column(db.ForeignKey("rhythms.id"), nullable=False)
    team_id = db.Column(db.ForeignKey("teams.id"), nullable=False)
    tempo_bpm_used = db.Column(db.Float, nullable=False)
    tolerance_preset = db.Column(db.String(20), nullable=False, default="gentle")
    status = db.Column(
        db.Enum(*ROUND_STATUSES, name="round_status", native_enum=False),
        nullable=False,
        default="pending",
    )
    recording_key = db.Column(db.String(255))
    recording_deleted_at = db.Column(db.DateTime(timezone=True))
    countin_start_s = db.Column(db.Float)  # recording start -> count-in downbeat (s)
    latency_ms_used = db.Column(db.Float)
    # Backing "bed" track that played under the team's turn (null = no music).
    backing_track_id = db.Column(db.ForeignKey("backing_tracks.id", ondelete="SET NULL"))
    music_start_s = db.Column(db.Float)  # recording start -> bed beat 0 (s)
    music_volume_used = db.Column(db.Float)
    error_message = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    session = db.relationship("ClassSession", back_populates="rounds")
    rhythm = db.relationship("Rhythm")
    team = db.relationship("Team")
    backing_track = db.relationship("BackingTrack")
    score = db.relationship("Score", back_populates="round", uselist=False)

    def to_dict(self, include_score: bool = True):
        d = {
            "id": self.id,
            "session_id": self.session_id,
            "game_mode": self.game_mode.value if self.game_mode else None,
            "rhythm_id": self.rhythm_id,
            "team_id": self.team_id,
            "tempo_bpm_used": self.tempo_bpm_used,
            "tolerance_preset": self.tolerance_preset,
            "status": self.status,
            "has_recording": bool(self.recording_key and not self.recording_deleted_at),
            "backing_track_id": self.backing_track_id,
            "music_volume_used": self.music_volume_used,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_score:
            d["score"] = self.score.to_dict() if self.score else None
        return d


CATEGORY_FIELDS = ("pattern_accuracy", "timing_accuracy", "tempo_consistency", "completion")


class Score(db.Model):
    """Machine score for a round. Instructor overrides are stored alongside, never replacing it."""

    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.ForeignKey("rounds.id"), nullable=False, unique=True)
    pattern_accuracy = db.Column(db.Float, nullable=False)
    timing_accuracy = db.Column(db.Float, nullable=False)
    tempo_consistency = db.Column(db.Float, nullable=False)
    completion = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    detected_onsets = db.Column(db.JSON, nullable=False, default=list)
    matched_pairs = db.Column(db.JSON, nullable=False, default=dict)  # full alignment detail
    confidence = db.Column(db.Float, nullable=False)
    needs_review = db.Column(db.Boolean, nullable=False, default=False)
    review_reasons = db.Column(db.JSON, nullable=False, default=list)
    confirmed_at = db.Column(db.DateTime(timezone=True))
    is_override = db.Column(db.Boolean, nullable=False, default=False)
    override_values = db.Column(db.JSON)  # adjusted categories / total
    override_reason = db.Column(db.String(255))
    overridden_by = db.Column(db.ForeignKey("instructors.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    round = db.relationship("Round", back_populates="score")

    @property
    def machine(self) -> dict:
        d = {f: getattr(self, f) for f in CATEGORY_FIELDS}
        d["total"] = self.total
        return d

    @property
    def effective(self) -> dict:
        if self.is_override and self.override_values:
            return {**self.machine, **self.override_values}
        return self.machine

    @property
    def effective_total(self) -> float:
        return float(self.effective["total"])

    def to_dict(self):
        return {
            "id": self.id,
            "round_id": self.round_id,
            "machine": self.machine,
            "effective": self.effective,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "review_reasons": self.review_reasons or [],
            "confirmed": self.confirmed_at is not None,
            "is_override": self.is_override,
            "override_reason": self.override_reason,
            "detected_onsets": self.detected_onsets,
            "alignment": self.matched_pairs,
        }


class Activity(db.Model):
    """A saved, reusable sequence of rhythms (e.g. 'Tuesday Latin set')."""

    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    rhythm_ids = db.Column(db.JSON, nullable=False, default=list)
    settings = db.Column(db.JSON, nullable=False, default=dict)
    created_by = db.Column(db.ForeignKey("instructors.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rhythm_ids": self.rhythm_ids,
            "settings": self.settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DisplayPairing(db.Model):
    """Short code shown on the dashboard so the TV can join a session without logging in."""

    __tablename__ = "display_pairings"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.ForeignKey("sessions.id"), nullable=False, index=True)
    code = db.Column(db.String(8), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
