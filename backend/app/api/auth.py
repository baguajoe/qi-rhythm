import re

from flask import Blueprint, abort, jsonify
from flask_jwt_extended import create_access_token

from ..extensions import db
from ..models import Instructor, Organization
from ..models.org import ORG_TYPES
from .util import instructor_required, json_body, require_str

bp = Blueprint("auth", __name__)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 10


def _token_for(inst: Instructor) -> str:
    return create_access_token(
        identity=str(inst.id),
        additional_claims={"kind": "instructor", "org": inst.organization_id, "role": inst.role},
    )


def _auth_payload(inst: Instructor):
    return {
        "access_token": _token_for(inst),
        "instructor": inst.to_dict(),
        "organization": inst.organization.to_dict(),
    }


@bp.post("/register")
def register():
    data = json_body()
    org_name = require_str(data, "organization_name", "your organization's name", 160)
    org_type = data.get("organization_type", "senior_center")
    if org_type not in ORG_TYPES:
        abort(400, "Please choose an organization type.")
    name = require_str(data, "display_name", "your name", 120)
    email = require_str(data, "email", "an email address", 254).lower()
    if not EMAIL.match(email):
        abort(400, "Please enter a valid email address.")
    password = data.get("password") or ""
    if len(password) < MIN_PASSWORD:
        abort(400, f"Please choose a password with at least {MIN_PASSWORD} characters.")
    if Instructor.query.filter_by(email=email).first():
        abort(409, "An account with that email already exists. Try signing in.")

    org = Organization(name=org_name, type=org_type)
    db.session.add(org)
    db.session.flush()
    inst = Instructor(organization_id=org.id, display_name=name, email=email, role="admin")
    inst.set_password(password)
    db.session.add(inst)
    db.session.commit()
    return jsonify(_auth_payload(inst)), 201


@bp.post("/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    inst = Instructor.query.filter_by(email=email).one_or_none()
    if inst is None or not inst.check_password(str(data.get("password", ""))):
        abort(401, "That email and password don't match. Please try again.")
    return jsonify(_auth_payload(inst))


@bp.get("/me")
@instructor_required
def me(me: Instructor):
    return jsonify(instructor=me.to_dict(), organization=me.organization.to_dict())
