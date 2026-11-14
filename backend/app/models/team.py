from ..extensions import db
from .base import utcnow


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey("organizations.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#1b3a5c")
    mascot_icon = db.Column(db.String(40))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    wins = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    total_points = db.Column(db.Float, nullable=False, default=0.0)

    organization = db.relationship("Organization", back_populates="teams")
    participants = db.relationship(
        "Participant",
        back_populates="team",
        cascade="all, delete-orphan",
        order_by="Participant.id",
    )

    def to_dict(self, include_participants: bool = True):
        d = {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "mascot_icon": self.mascot_icon,
            "is_active": self.is_active,
            "wins": self.wins,
            "losses": self.losses,
            "total_points": round(self.total_points, 1),
        }
        if include_participants:
            d["participants"] = [p.to_dict() for p in self.participants]
        return d


class Participant(db.Model):
    """A team member, identified by alias ONLY. Do not add any other personal fields."""

    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    team = db.relationship("Team", back_populates="participants")

    def to_dict(self):
        return {"id": self.id, "alias": self.alias}
