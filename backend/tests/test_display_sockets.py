from datetime import timedelta

import pytest

from app.extensions import socketio
from app.models import DisplayPairing
from app.models.base import utcnow
from app.sockets.state import clear_live

from .test_rounds_api import play_turn, setup_class


def events_named(client, name):
    return [e["args"][0] for e in client.get_received() if e["name"] == name]


def pair_display(client, h, sess_id):
    code = client.post(f"/api/sessions/{sess_id}/display-code", headers=h).get_json()
    assert len(code["code"]) == 6 and code["path"].startswith(f"/display/{sess_id}?code=")
    res = client.post("/api/display/pair", json={"code": code["code"].lower()})
    assert res.status_code == 200
    return res.get_json()["display_token"]


def test_display_pairing_and_state(client, app):
    h, sess, clave, t1, _ = setup_class(client)
    clear_live(sess["id"])
    token = pair_display(client, h, sess["id"])
    state = client.get("/api/display/state", headers={"Authorization": f"Bearer {token}"})
    assert state.get_json()["session_id"] == sess["id"]
    # display token cannot use instructor endpoints
    assert client.get("/api/teams", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.post("/api/display/pair", json={"code": "ZZZZZZ"}).status_code == 404


def test_expired_code_rejected(client, db):
    h, sess, *_ = setup_class(client)
    code = client.post(f"/api/sessions/{sess['id']}/display-code", headers=h).get_json()["code"]
    p = DisplayPairing.query.filter_by(code=code).one()
    p.expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert client.post("/api/display/pair", json={"code": code}).status_code == 404


def test_socket_requires_valid_token(app, client):
    setup_class(client)
    sio = socketio.test_client(app, auth={"token": "garbage"})
    assert not sio.is_connected()
    sio2 = socketio.test_client(app)
    assert not sio2.is_connected()


def test_display_follows_instructor_and_rest_events(app, client):
    h, sess, clave, t1, _ = setup_class(client)
    clear_live(sess["id"])
    instructor_token = h["Authorization"].split()[1]
    display = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    inst = socketio.test_client(app, auth={"token": instructor_token})
    assert display.is_connected() and inst.is_connected()

    assert display.emit("join_session", {"session_id": sess["id"]}, callback=True) == {"ok": True}
    assert inst.emit("join_session", {"session_id": sess["id"]}, callback=True) == {"ok": True}
    snap = events_named(display, "session:state")[0]
    assert snap["live"]["phase"] == "idle" and snap["scoreboard"]["teams"] == []

    inst.emit("control:focus", {"team_id": t1["id"], "rhythm_id": clave["id"]})
    inst.emit("control:countin", {"count": 3})
    got = display.get_received()
    names = [e["name"] for e in got]
    assert "session:focus" in names and "round:countin" in names
    assert next(e for e in got if e["name"] == "round:countin")["args"][0] == {"count": 3}
    assert events_named(inst, "round:countin") == []  # sender is skipped

    # the display cannot drive the class
    assert display.emit("control:countin", {"count": 1}, callback=True)["ok"] is False

    # REST-driven round lifecycle reaches the display
    res, _, _ = play_turn(client, h, sess, clave, t1)
    assert res.status_code == 201
    names = [e["name"] for e in display.get_received()]
    for ev in (
        "round:started",
        "round:reference_playing",
        "round:countin",
        "round:analyzing",
        "round:scored",
        "scoreboard:updated",
    ):
        assert ev in names, ev

    # reconnect: a fresh display client gets a correct snapshot
    display.disconnect()
    again = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    again.emit("join_session", {"session_id": sess["id"]})
    snap = events_named(again, "session:state")[0]
    assert snap["live"]["phase"] == "scored"
    assert snap["round"]["status"] == "scored"
    assert snap["scoreboard"]["teams"][0]["turns"] == 1
    assert snap["live"]["focus"]["team_id"] == t1["id"]


def test_display_token_limited_to_its_session(app, client):
    h, sess, *_ = setup_class(client)
    other = client.post("/api/sessions", json={}, headers=h).get_json()["session"]
    display = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    assert display.emit("join_session", {"session_id": other["id"]}, callback=True)["ok"] is False


def test_end_session_shows_ended(app, client):
    h, sess, *_ = setup_class(client)
    display = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    display.emit("join_session", {"session_id": sess["id"]})
    display.get_received()
    client.post(f"/api/sessions/{sess['id']}/end", headers=h)
    assert events_named(display, "session:ended")
    assert client.post(f"/api/sessions/{sess['id']}/display-code", headers=h).status_code == 409


# ---------------------------------------------------------------- control-event authorization

from app.sockets.handlers import CONTROL_EVENTS  # noqa: E402


def _joined_clients(app, client):
    h, sess, *_ = setup_class(client)
    clear_live(sess["id"])
    inst = socketio.test_client(app, auth={"token": h["Authorization"].split()[1]})
    tv1 = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    tv2 = socketio.test_client(app, auth={"token": pair_display(client, h, sess["id"])})
    for c in (inst, tv1, tv2):
        assert c.emit("join_session", {"session_id": sess["id"]}, callback=True) == {"ok": True}
        c.get_received()
    return h, sess, inst, tv1, tv2


@pytest.mark.parametrize("event", sorted(CONTROL_EVENTS))
def test_only_the_instructor_can_send_control_events(app, client, event):
    _, _, inst, tv1, tv2 = _joined_clients(app, client)
    payload = {"count": 2, "index": 1, "rms": 0.2, "title": "x"}

    # Instructor: accepted and relayed to every display under the public event name.
    assert inst.emit(event, payload, callback=True) == {"ok": True}
    for tv in (tv1, tv2):
        got = [e for e in tv.get_received() if e["name"] == CONTROL_EVENTS[event]]
        assert got and got[0]["args"][0] == payload

    # Display: refused, and nothing reaches the other display or the instructor.
    ack = tv1.emit(event, payload, callback=True)
    assert ack["ok"] is False and "instructor" in ack["error"]
    assert tv2.get_received() == []
    assert inst.get_received() == []


def test_instructor_must_join_before_controlling(app, client):
    h, sess, *_ = setup_class(client)
    inst = socketio.test_client(app, auth={"token": h["Authorization"].split()[1]})
    assert inst.emit("control:countin", {"count": 1}, callback=True)["ok"] is False


def test_instructor_from_another_org_cannot_join(app, client):
    _, sess, *_ = setup_class(client)
    from .helpers import auth_headers

    other = auth_headers(client, email="else@example.com", org="Elsewhere")
    sio = socketio.test_client(app, auth={"token": other["Authorization"].split()[1]})
    assert sio.emit("join_session", {"session_id": sess["id"]}, callback=True)["ok"] is False
    assert sio.emit("join_session", {"session_id": "nope"}, callback=True)["ok"] is False


def test_expired_display_token_cannot_connect(app, client):
    from flask_jwt_extended import create_access_token

    _, sess, *_ = setup_class(client)
    with app.test_request_context():
        token = create_access_token(
            identity=f"display:{sess['id']}",
            additional_claims={"kind": "display", "session_id": sess["id"]},
            expires_delta=timedelta(seconds=-5),
        )
    assert not socketio.test_client(app, auth={"token": token}).is_connected()


def test_oversized_control_payload_is_refused(app, client):
    _, _, inst, tv1, _ = _joined_clients(app, client)
    big = {f"k{i}": i for i in range(30)}
    assert inst.emit("control:focus", big, callback=True)["ok"] is False
    assert tv1.get_received() == []
