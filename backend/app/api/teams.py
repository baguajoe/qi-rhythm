from flask import Blueprint, abort, jsonify, request

from ..extensions import db
from ..models import Instructor, Participant, Team
from .util import HEX_COLOR, get_owned, instructor_required, json_body, require_str

bp = Blueprint("teams", __name__)

MASCOT_ICONS = {"sun", "bird", "star", "flower", "drum", "music", "tree", "wave", "heart", "moon"}
MAX_TEAMS = 50
MAX_PARTICIPANTS = 40


def _apply(team: Team, data: dict, partial: bool) -> None:
    if "name" in data or not partial:
        team.name = require_str(data, "name", "a team name", 80)
    if "color" in data or not partial:
        color = data.get("color", "#1f4e99")
        if not isinstance(color, str) or not HEX_COLOR.match(color):
            abort(400, "Team color must look like #1f4e99.")
        team.color = color.lower()
    if "mascot_icon" in data:
        icon = data["mascot_icon"] or None
        if icon is not None and icon not in MASCOT_ICONS:
            abort(400, "Please choose one of the listed icons.")
        team.mascot_icon = icon
    if "is_active" in data:
        team.is_active = bool(data["is_active"])


@bp.get("")
@instructor_required
def list_teams(me: Instructor):
    q = Team.query.filter_by(organization_id=me.organization_id)
    if request.args.get("include_inactive") not in ("1", "true"):
        q = q.filter_by(is_active=True)
    return jsonify(teams=[t.to_dict() for t in q.order_by(Team.id)])


@bp.post("")
@instructor_required
def create_team(me: Instructor):
    if Team.query.filter_by(organization_id=me.organization_id).count() >= MAX_TEAMS:
        abort(400, "You've reached the team limit. Archive a team to add another.")
    team = Team(organization_id=me.organization_id)
    _apply(team, json_body(), partial=False)
    db.session.add(team)
    db.session.commit()
    return jsonify(team=team.to_dict()), 201


@bp.get("/<int:team_id>")
@instructor_required
def get_team(me: Instructor, team_id: int):
    return jsonify(team=get_owned(Team, team_id, me).to_dict())


@bp.patch("/<int:team_id>")
@instructor_required
def update_team(me: Instructor, team_id: int):
    team = get_owned(Team, team_id, me)
    _apply(team, json_body(), partial=True)
    db.session.commit()
    return jsonify(team=team.to_dict())


@bp.post("/<int:team_id>/participants")
@instructor_required
def add_participant(me: Instructor, team_id: int):
    team = get_owned(Team, team_id, me)
    data = json_body()
    unexpected = set(data) - {"alias"}
    if unexpected:
        # Privacy guard: participants are identified by alias only.
        abort(400, "Only an alias (nickname) can be stored for participants.")
    if len(team.participants) >= MAX_PARTICIPANTS:
        abort(400, "This team already has the maximum number of members.")
    p = Participant(team_id=team.id, alias=require_str(data, "alias", "a nickname", 40))
    db.session.add(p)
    db.session.commit()
    return jsonify(participant=p.to_dict(), team=team.to_dict()), 201


@bp.delete("/<int:team_id>/participants/<int:participant_id>")
@instructor_required
def remove_participant(me: Instructor, team_id: int, participant_id: int):
    team = get_owned(Team, team_id, me)
    p = db.session.get(Participant, participant_id)
    if p is None or p.team_id != team.id:
        abort(404, "Not found.")
    db.session.delete(p)
    db.session.commit()
    return jsonify(team=team.to_dict())
