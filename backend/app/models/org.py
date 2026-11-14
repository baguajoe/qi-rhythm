from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .base import utcnow

ORG_TYPES = ("senior_center", "assisted_living", "community_org", "adult_day", "other")
ROLES = ("admin", "instructor")


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    type = db.Column(
        db.Enum(*ORG_TYPES, name="org_type", native_enum=False), nullable=False, default="other"
    )
    timezone = db.Column(db.String(64), nullable=False, default="America/New_York")
    recording_retention_days = db.Column(db.Integer, nullable=False, default=7)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    instructors = db.relationship("Instructor", back_populates="organization")
    teams = db.relationship("Team", back_populates="organization")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "timezone": self.timezone,
            "recording_retention_days": self.recording_retention_days,
        }


class Instructor(db.Model):
    __tablename__ = "instructors"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Enum(*ROLES, name="instructor_role", native_enum=False),
        nullable=False,
        default="instructor",
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    organization = db.relationship("Organization", back_populates="instructors")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "display_name": self.display_name,
            "email": self.email,
            "role": self.role,
        }
