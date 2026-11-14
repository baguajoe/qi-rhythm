from flask import Blueprint, abort, jsonify, request

from ..extensions import db
from ..models import Genre, Instructor, Rhythm
from ..models.rhythm import DIFFICULTIES
from .util import instructor_required

bp = Blueprint("rhythms", __name__)


@bp.get("/genres")
@instructor_required
def genres(me: Instructor):
    rows = Genre.query.order_by(Genre.id).all()
    counts = dict(
        db.session.query(Rhythm.genre_id, db.func.count(Rhythm.id)).group_by(Rhythm.genre_id).all()
    )
    return jsonify(genres=[{**g.to_dict(), "rhythm_count": counts.get(g.id, 0)} for g in rows])


@bp.get("/rhythms")
@instructor_required
def rhythms(me: Instructor):
    q = Rhythm.query.join(Genre)
    genre = request.args.get("genre")
    if genre:
        q = (
            q.filter(Genre.slug == genre)
            if not genre.isdigit()
            else q.filter(Genre.id == int(genre))
        )
    difficulty = request.args.get("difficulty")
    if difficulty:
        if difficulty not in DIFFICULTIES:
            abort(400, "Difficulty must be beginner, intermediate, or advanced.")
        q = q.filter(Rhythm.difficulty == difficulty)
    order = db.case({d: i for i, d in enumerate(DIFFICULTIES)}, value=Rhythm.difficulty)
    return jsonify(rhythms=[r.to_dict() for r in q.order_by(Genre.id, order, Rhythm.id)])


@bp.get("/rhythms/<int:rhythm_id>")
@instructor_required
def rhythm(me: Instructor, rhythm_id: int):
    r = db.session.get(Rhythm, rhythm_id)
    if r is None:
        abort(404, "That rhythm wasn't found.")
    return jsonify(rhythm=r.to_dict(), genre=r.genre.to_dict())
