from ..extensions import db

DIFFICULTIES = ("beginner", "intermediate", "advanced")
SOURCES = ("original", "licensed")


class Genre(db.Model):
    __tablename__ = "genres"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    cultural_notes = db.Column(db.Text, nullable=False, default="")

    rhythms = db.relationship("Rhythm", back_populates="genre", order_by="Rhythm.id")

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "cultural_notes": self.cultural_notes,
        }


class Rhythm(db.Model):
    __tablename__ = "rhythms"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    genre_id = db.Column(db.ForeignKey("genres.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    difficulty = db.Column(
        db.Enum(*DIFFICULTIES, name="difficulty", native_enum=False), nullable=False, index=True
    )
    bpm = db.Column(db.Float, nullable=False)
    time_signature = db.Column(db.String(8), nullable=False, default="4/4")
    length_beats = db.Column(db.Float, nullable=False)
    pattern = db.Column(db.JSON, nullable=False)
    # Hook: original Cubase-recorded reference audio uploaded to R2 replaces the Tone.js synth.
    reference_audio_key = db.Column(db.String(255))
    source = db.Column(
        db.Enum(*SOURCES, name="rhythm_source", native_enum=False),
        nullable=False,
        default="original",
    )
    license_notes = db.Column(db.Text, nullable=False, default="")
    created_by = db.Column(db.ForeignKey("instructors.id"))  # null = bundled library

    genre = db.relationship("Genre", back_populates="rhythms")

    @property
    def engine_pattern(self) -> dict:
        """Pattern dict ready for the analysis engine (includes length)."""
        return {**self.pattern, "length_beats": self.length_beats}

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "genre_id": self.genre_id,
            "genre_slug": self.genre.slug if self.genre else None,
            "title": self.title,
            "difficulty": self.difficulty,
            "bpm": self.bpm,
            "time_signature": self.time_signature,
            "length_beats": self.length_beats,
            "pattern": self.pattern,
            "reference_audio_key": self.reference_audio_key,
            "source": self.source,
            "license_notes": self.license_notes,
        }
