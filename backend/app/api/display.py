"""Pairing the TV/projector Display View without an instructor login."""

import secrets
from datetime import timedelta

from flask import Blueprint, abort, current_app, jsonify
from flask_jwt_extended import create_access_token, get_jwt, jwt_required

from ..extensions import db
from ..models import ClassSession, DisplayPairing, Instructor
from ..models.base import utcnow
from ..sockets.state import snapshot
from .util import get_owned, instructor_required, json_body

bp = Blueprint("display", __name__)

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
CODE_LENGTH = 6
DISPLAY_TOKEN_HOURS = 12


def _new_code() -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not DisplayPairing.query.filter_by(code=code).first():
            return code
    raise RuntimeError("could not allocate a display code")


@bp.post("/sessions/<int:session_id>/display-code")
@instructor_required
def create_code(me: Instructor, session_id: int):
    sess = get_owned(ClassSession, session_id, me)
    if sess.ended_at:
        abort(409, "This class has ended.")
    minutes = current_app.config["DISPLAY_TOKEN_MINUTES"]
    pairing = DisplayPairing(
        session_id=sess.id, code=_new_code(), expires_at=utcnow() + timedelta(minutes=minutes)
    )
    db.session.add(pairing)
    db.session.commit()
    return (
        jsonify(
            code=pairing.code,
            expires_at=pairing.expires_at.isoformat(),
            session_id=sess.id,
            path=f"/display/{sess.id}?code={pairing.code}",
        ),
        201,
    )


@bp.post("/display/pair")
def pair():
    data = json_body()
    code = str(data.get("code", "")).strip().upper().replace(" ", "").replace("-", "")
    pairing = DisplayPairing.query.filter_by(code=code).one_or_none()
    if pairing is None or pairing.expires_at < utcnow():
        abort(404, "That code didn't work. Ask the instructor for a new code.")
    sess = db.session.get(ClassSession, pairing.session_id)
    if sess is None or sess.ended_at:
        abort(404, "That class has ended.")
    token = create_access_token(
        identity=f"display:{sess.id}",
        additional_claims={"kind": "display", "session_id": sess.id},
        expires_delta=timedelta(hours=DISPLAY_TOKEN_HOURS),
    )
    return jsonify(display_token=token, session_id=sess.id)


@bp.get("/display/state")
@jwt_required()
def state():
    claims = get_jwt()
    if claims.get("kind") != "display":
        abort(403, "Display token required.")
    sess = db.session.get(ClassSession, int(claims["session_id"]))
    if sess is None:
        abort(404, "Not found.")
    return jsonify(snapshot(sess))
