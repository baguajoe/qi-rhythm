from ..extensions import db
from .base import utcnow


class CalibrationProfile(db.Model):
    __tablename__ = "calibration_profiles"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    device_label = db.Column(db.String(120), nullable=False)
    latency_offset_ms = db.Column(db.Float, nullable=False, default=0.0)
    noise_floor_db = db.Column(db.Float)
    onset_threshold = db.Column(db.Float, nullable=False, default=0.07)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "device_label": self.device_label,
            "latency_offset_ms": self.latency_offset_ms,
            "noise_floor_db": self.noise_floor_db,
            "onset_threshold": self.onset_threshold,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
