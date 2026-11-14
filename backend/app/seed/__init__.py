"""Idempotent seeding: bundled rhythm library and an optional demo organization."""

import os

from ..extensions import db
from ..models import Genre, Instructor, Organization, Rhythm, Team
from .library import GENRES


def seed_library() -> tuple[int, int]:
    """Upsert genres and rhythms by slug. Returns (genre_count, rhythm_count)."""
    n_r = 0
    for g in GENRES:
        genre = Genre.query.filter_by(slug=g["slug"]).one_or_none() or Genre(slug=g["slug"])
        genre.name = g["name"]
        genre.description = g["description"]
        genre.cultural_notes = g["cultural_notes"]
        db.session.add(genre)
        db.session.flush()
        for r in g["rhythms"]:
            rhythm = Rhythm.query.filter_by(slug=r["slug"]).one_or_none() or Rhythm(slug=r["slug"])
            for key, value in r.items():
                setattr(rhythm, key, value)
            rhythm.genre_id = genre.id
            db.session.add(rhythm)
            n_r += 1
    db.session.commit()
    return len(GENRES), n_r


def seed_demo() -> Instructor:
    """Create a demo organization + instructor + two teams (development only)."""
    email = os.getenv("DEMO_EMAIL", "demo@example.com")
    existing = Instructor.query.filter_by(email=email).one_or_none()
    if existing:
        return existing
    org = Organization(name="Sunrise Community Center", type="senior_center")
    db.session.add(org)
    db.session.flush()
    inst = Instructor(
        organization_id=org.id, display_name="Demo Instructor", email=email, role="admin"
    )
    inst.set_password(os.getenv("DEMO_PASSWORD", "rhythm-demo-123"))
    db.session.add(inst)
    db.session.add_all(
        [
            Team(organization_id=org.id, name="Sunflowers", color="#b35900", mascot_icon="sun"),
            Team(organization_id=org.id, name="Blue Jays", color="#1f4e99", mascot_icon="bird"),
        ]
    )
    db.session.commit()
    return inst
