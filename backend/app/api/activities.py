"""Saved Activities: reusable rhythm sequences (e.g. 'Tuesday Latin set')."""

from flask import Blueprint, abort, jsonify

from ..extensions import db
from ..models import Activity, ClassSession, Instructor, Rhythm
from .util import get_owned, instructor_required, json_body, require_str

bp = Blueprint("activities", __name__)
MAX_RHYTHMS = 30


def _payload(a: Activity) -> dict:
    rhythms = {r.id: r for r in Rhythm.query.filter(Rhythm.id.in_(a.rhythm_ids or [])).all()}
    return {
        **a.to_dict(),
        "rhythms": [
            {"id": rid, "title": rhythms[rid].title, "difficulty": rhythms[rid].difficulty}
            for rid in a.rhythm_ids
            if rid in rhythms
        ],
    }


@bp.get("")
@instructor_required
def list_activities(me: Instructor):
    rows = (
        Activity.query.filter_by(organization_id=me.organization_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .all()
    )
    return jsonify(activities=[_payload(a) for a in rows])


@bp.post("")
@instructor_required
def create_activity(me: Instructor):
    data = json_body()
    name = require_str(data, "name", "a name for this activity", 120)
    if data.get("from_session_id"):
        sess = get_owned(ClassSession, int(data["from_session_id"]), me)
        ids = []
        for rnd in sess.rounds:
            if rnd.rhythm_id not in ids:
                ids.append(rnd.rhythm_id)
    else:
        raw = data.get("rhythm_ids")
        if not isinstance(raw, list):
            abort(400, "Please choose at least one rhythm.")
        try:
            ids = [int(i) for i in raw]
        except (TypeError, ValueError):
            abort(400, "Rhythm list is not valid.")
    if not ids:
        abort(400, "Play at least one rhythm before saving an activity.")
    if len(ids) > MAX_RHYTHMS:
        abort(400, f"An activity can hold up to {MAX_RHYTHMS} rhythms.")
    found = {r.id for r in Rhythm.query.filter(Rhythm.id.in_(ids)).all()}
    if len(found) != len(set(ids)):
        abort(400, "One of those rhythms wasn't found.")
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    a = Activity(
        organization_id=me.organization_id,
        name=name,
        rhythm_ids=ids,
        settings=settings,
        created_by=me.id,
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(activity=_payload(a)), 201


@bp.delete("/<int:activity_id>")
@instructor_required
def delete_activity(me: Instructor, activity_id: int):
    a = get_owned(Activity, activity_id, me)
    db.session.delete(a)
    db.session.commit()
    return jsonify(deleted=True)
