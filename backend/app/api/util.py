"""Shared helpers for API blueprints."""

import re
from functools import wraps

from flask import abort, request
from flask_jwt_extended import get_jwt, jwt_required, verify_jwt_in_request

from ..extensions import db
from ..models import Instructor

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Expected a JSON object.")
    return data


def require_str(data: dict, key: str, label: str, max_len: int, min_len: int = 1) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value.strip()) < min_len:
        abort(400, f"Please enter {label}.")
    value = value.strip()
    if len(value) > max_len:
        abort(400, f"{label.capitalize()} must be {max_len} characters or fewer.")
    return value


def instructor_required(fn):
    """JWT-protect a route and pass the current Instructor as ``me``."""

    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("kind") != "instructor":
            abort(403, "Instructor sign-in required.")
        me = db.session.get(Instructor, int(claims["sub"]))
        if me is None:
            abort(401, "Please sign in again.")
        return fn(me, *args, **kwargs)

    return wrapper


def optional_claims() -> dict | None:
    try:
        verify_jwt_in_request(optional=True)
    except Exception:  # noqa: BLE001 - invalid token behaves like no token
        return None
    return get_jwt() or None


def get_owned(model, obj_id: int, me: Instructor):
    """Fetch an org-scoped object, 404 if it belongs to another organization."""
    obj = db.session.get(model, obj_id)
    if obj is None or getattr(obj, "organization_id", None) != me.organization_id:
        abort(404, "Not found.")
    return obj
