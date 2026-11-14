"""Socket.IO handlers. One room per class session ("session:<id>").

Clients connect with ``auth={"token": <JWT>}``: either an instructor access token or a display
token from the pairing flow. Only instructors may emit control events; they are relayed to the
room so the Display View can follow live (count-in, beat lights, input level).
"""

from __future__ import annotations

from flask import request
from flask_jwt_extended import decode_token
from flask_socketio import emit, join_room, leave_room

from ..extensions import db, socketio
from ..models import ClassSession, Instructor
from .broadcast import room_for
from .state import snapshot, update_live

_CLIENTS: dict[str, dict] = {}  # sid -> claims

# Relayed control events: client event -> (room event, live-state changes)
CONTROL_EVENTS = {
    "control:focus": "session:focus",  # team/rhythm selected on the dashboard
    "control:reference": "round:reference_playing",  # reference (or preview) starts
    "control:beat": "round:beat",  # a reference hit just sounded
    "control:countin": "round:countin",
    "control:recording": "round:recording",
    "control:level": "round:level",
    "control:idle": "session:idle",
}
PHASE_FOR = {
    "control:reference": "reference",
    "control:countin": "countin",
    "control:recording": "recording",
    "control:idle": "idle",
}
MAX_PAYLOAD_KEYS = 12


def _claims_from_auth(auth) -> dict | None:
    token = (auth or {}).get("token") if isinstance(auth, dict) else None
    if not token:
        return None
    try:
        return decode_token(token)
    except Exception:  # noqa: BLE001 - expired/invalid token
        return None


def _may_join(claims: dict, sess: ClassSession) -> bool:
    if claims.get("kind") == "display":
        return int(claims.get("session_id", -1)) == sess.id
    if claims.get("kind") == "instructor":
        inst = db.session.get(Instructor, int(claims["sub"]))
        return inst is not None and inst.organization_id == sess.organization_id
    return False


@socketio.on("connect")
def on_connect(auth=None):
    claims = _claims_from_auth(auth)
    if claims is None:
        return False  # reject connection
    _CLIENTS[request.sid] = {**claims, "rooms": set()}
    return True


@socketio.on("disconnect")
def on_disconnect(*_args):
    _CLIENTS.pop(request.sid, None)


@socketio.on("join_session")
def on_join(data):
    client = _CLIENTS.get(request.sid)
    try:
        session_id = int((data or {}).get("session_id"))
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad session id"}
    sess = db.session.get(ClassSession, session_id)
    if client is None or sess is None or not _may_join(client, sess):
        return {"ok": False, "error": "not allowed"}
    for room in list(client["rooms"]):
        leave_room(room)
    join_room(room_for(sess.id))
    client["rooms"] = {room_for(sess.id)}
    client["session_id"] = sess.id
    emit("session:state", snapshot(sess))
    return {"ok": True}


def _relay(event: str, data):
    client = _CLIENTS.get(request.sid)
    if not client or client.get("kind") != "instructor" or "session_id" not in client:
        return {"ok": False, "error": "only the instructor can control the class"}
    payload = data if isinstance(data, dict) else {}
    if len(payload) > MAX_PAYLOAD_KEYS:
        return {"ok": False, "error": "payload too large"}
    session_id = client["session_id"]
    changes = {}
    if event in PHASE_FOR:
        changes["phase"] = PHASE_FOR[event]
    if event == "control:focus":
        changes.update(focus=payload)
    elif event == "control:reference":
        changes.update(reference=payload, count=None)
    elif event == "control:countin":
        changes.update(count=payload.get("count"))
    elif event == "control:recording":
        changes.update(count=None)
    if changes:
        update_live(session_id, **changes)
    socketio.emit(CONTROL_EVENTS[event], payload, to=room_for(session_id), skip_sid=request.sid)
    return {"ok": True}


def _make_handler(event):
    def handler(data=None):
        return _relay(event, data)

    handler.__name__ = f"on_{event.replace(':', '_')}"
    return handler


for _event in CONTROL_EVENTS:
    socketio.on_event(_event, _make_handler(_event))
