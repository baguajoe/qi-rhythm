"""API contract: every REST route is classified, rejects bad credentials, and has a happy path.

If you add a route, add it to ROUTES (the meta-test fails otherwise) and exercise it in
``test_every_route_has_a_happy_path``.
"""

import io
from datetime import timedelta

import pytest
from flask import request, request_finished
from flask_jwt_extended import create_access_token

from .test_display_sockets import pair_display
from .test_rounds_api import play_turn, setup_class, wav

PUBLIC, INSTRUCTOR, DISPLAY = "public", "instructor", "display"

ROUTES = {
    ("GET", "/health"): PUBLIC,
    ("POST", "/api/auth/register"): PUBLIC,
    ("POST", "/api/auth/login"): PUBLIC,
    ("POST", "/api/display/pair"): PUBLIC,
    ("GET", "/api/display/state"): DISPLAY,
    ("GET", "/api/auth/me"): INSTRUCTOR,
    ("GET", "/api/teams"): INSTRUCTOR,
    ("POST", "/api/teams"): INSTRUCTOR,
    ("GET", "/api/teams/<int:team_id>"): INSTRUCTOR,
    ("PATCH", "/api/teams/<int:team_id>"): INSTRUCTOR,
    ("POST", "/api/teams/<int:team_id>/participants"): INSTRUCTOR,
    ("DELETE", "/api/teams/<int:team_id>/participants/<int:participant_id>"): INSTRUCTOR,
    ("GET", "/api/genres"): INSTRUCTOR,
    ("GET", "/api/rhythms"): INSTRUCTOR,
    ("GET", "/api/rhythms/<int:rhythm_id>"): INSTRUCTOR,
    ("GET", "/api/calibration"): INSTRUCTOR,
    ("POST", "/api/calibration"): INSTRUCTOR,
    ("POST", "/api/calibration/analyze/noise"): INSTRUCTOR,
    ("POST", "/api/calibration/analyze/latency"): INSTRUCTOR,
    ("POST", "/api/calibration/analyze/sensitivity"): INSTRUCTOR,
    ("POST", "/api/sessions"): INSTRUCTOR,
    ("GET", "/api/sessions/<int:session_id>"): INSTRUCTOR,
    ("PATCH", "/api/sessions/<int:session_id>"): INSTRUCTOR,
    ("POST", "/api/sessions/<int:session_id>/end"): INSTRUCTOR,
    ("POST", "/api/sessions/<int:session_id>/rounds"): INSTRUCTOR,
    ("POST", "/api/sessions/<int:session_id>/display-code"): INSTRUCTOR,
    ("PATCH", "/api/rounds/<int:round_id>"): INSTRUCTOR,
    ("POST", "/api/rounds/<int:round_id>/recording"): INSTRUCTOR,
    ("GET", "/api/rounds/<int:round_id>/score"): INSTRUCTOR,
    ("POST", "/api/scores/<int:score_id>/override"): INSTRUCTOR,
    ("POST", "/api/scores/<int:score_id>/confirm"): INSTRUCTOR,
    ("POST", "/api/recordings/purge"): INSTRUCTOR,
    ("PATCH", "/api/organization"): INSTRUCTOR,
    ("GET", "/api/activities"): INSTRUCTOR,
    ("POST", "/api/activities"): INSTRUCTOR,
    ("DELETE", "/api/activities/<int:activity_id>"): INSTRUCTOR,
}


def concrete(rule: str) -> str:
    """Fill <int:...> placeholders with 1 (auth is checked before the object is looked up)."""
    import re

    return re.sub(r"<int:[a-z_]+>", "1", rule)


def test_route_table_matches_the_app(app):
    actual = {
        (m, r.rule)
        for r in app.url_map.iter_rules()
        if r.endpoint != "static"
        for m in r.methods - {"HEAD", "OPTIONS"}
    }
    assert actual == set(
        ROUTES
    ), f"unclassified: {sorted(actual - set(ROUTES))}; stale: {sorted(set(ROUTES) - actual)}"


PROTECTED = [k for k, v in ROUTES.items() if v != PUBLIC]


@pytest.fixture
def tokens(app, client):
    h, sess, *_ = setup_class(client)
    instructor = h["Authorization"].split()[1]
    display = pair_display(client, h, sess["id"])
    expired = create_access_token(
        identity="1", additional_claims={"kind": "instructor"}, expires_delta=timedelta(seconds=-5)
    )
    return {"instructor": instructor, "display": display, "expired": expired}


@pytest.mark.parametrize("method,rule", PROTECTED, ids=[f"{m} {r}" for m, r in PROTECTED])
def test_protected_routes_reject_bad_credentials(client, tokens, method, rule):
    url = concrete(rule)
    cases = {
        "no token": {},
        "malformed token": {"Authorization": "Bearer not-a-jwt"},
        "wrong scheme": {"Authorization": f"Basic {tokens['instructor']}"},
        "expired token": {"Authorization": f"Bearer {tokens['expired']}"},
    }
    for label, headers in cases.items():
        res = client.open(url, method=method, headers=headers, json={})
        assert res.status_code == 401, f"{label}: {res.status_code} {res.get_json()}"
        assert "sign in" in res.get_json()["error"].lower(), label

    # The wrong kind of token is refused too (display token on instructor routes and vice versa).
    wrong = tokens["display"] if ROUTES[(method, rule)] == INSTRUCTOR else tokens["instructor"]
    res = client.open(url, method=method, headers={"Authorization": f"Bearer {wrong}"}, json={})
    assert res.status_code == 403, res.get_json()


def test_every_route_has_a_happy_path(app, client):
    hits: set[tuple[str, str]] = set()

    def _record(sender, response, **_extra):  # noqa: ANN001
        if request.url_rule is not None and response.status_code < 300:
            hits.add((request.method, request.url_rule.rule))

    request_finished.connect(_record, app)

    try:
        assert client.get("/health").status_code == 200
        h, sess, clave, t1, t2 = setup_class(client)  # register, teams, session, rhythms
        sid = sess["id"]
        login = client.post(
            "/api/auth/login", json={"email": "coach@example.com", "password": "drumcircle1"}
        )
        assert login.status_code == 200
        ok = lambda res, code=200: res.status_code == code or pytest.fail(  # noqa: E731
            f"{res.request.method} {res.request.path}: {res.status_code} {res.get_json()}"
        )

        ok(client.get("/api/auth/me", headers=h))
        ok(client.get("/api/teams", headers=h))
        ok(client.get(f"/api/teams/{t1['id']}", headers=h))
        ok(client.patch(f"/api/teams/{t1['id']}", json={"mascot_icon": "drum"}, headers=h))
        p = client.post(f"/api/teams/{t1['id']}/participants", json={"alias": "Rosie"}, headers=h)
        ok(p, 201)
        pid = p.get_json()["participant"]["id"]
        ok(client.delete(f"/api/teams/{t1['id']}/participants/{pid}", headers=h))
        ok(client.get("/api/genres", headers=h))
        ok(client.get(f"/api/rhythms/{clave['id']}", headers=h))

        ok(client.get("/api/calibration", headers=h))
        ok(client.post("/api/calibration", json={"device_label": "Room"}, headers=h), 201)
        import numpy as np

        from app.audio.synth import SynthOptions, render

        quiet = (np.random.default_rng(0).standard_normal(48000 * 2) * 0.003).astype(np.float32)
        taps = render(
            {
                "count_in_beats": 0,
                "length_beats": 8,
                "events": [{"beat": b, "voice": "low"} for b in range(8)],
            },
            SynthOptions(bpm=100),
        )
        for step, audio, fields in [
            ("noise", wav(quiet, 48000), {}),
            (
                "latency",
                wav(taps.audio, taps.sr),
                {"click_times": str([taps.countin_start_s + b * 0.6 for b in range(8)])},
            ),
            ("sensitivity", wav(taps.audio, taps.sr), {"noise_floor_db": "-50"}),
        ]:
            ok(
                client.post(
                    f"/api/calibration/analyze/{step}",
                    headers=h,
                    data={"audio": (io.BytesIO(audio), "a.wav"), **fields},
                    content_type="multipart/form-data",
                )
            )

        ok(client.get(f"/api/sessions/{sid}", headers=h))
        ok(client.patch(f"/api/sessions/{sid}", json={"settings": {"volume": 0.5}}, headers=h))
        ok(client.post(f"/api/sessions/{sid}/display-code", headers=h), 201)
        disp = pair_display(client, h, sid)
        ok(client.get("/api/display/state", headers={"Authorization": f"Bearer {disp}"}))

        res, rnd, _ = play_turn(client, h, sess, clave, t1)  # rounds, PATCH round, recording
        ok(res, 201)
        score_id = res.get_json()["score"]["id"]
        ok(client.get(f"/api/rounds/{rnd['id']}/score", headers=h))
        ok(client.post(f"/api/scores/{score_id}/confirm", headers=h))
        ok(client.post(f"/api/scores/{score_id}/override", json={"total": 80}, headers=h))

        act = client.post(
            "/api/activities", json={"name": "Set", "from_session_id": sid}, headers=h
        )
        ok(act, 201)
        ok(client.get("/api/activities", headers=h))
        ok(client.delete(f"/api/activities/{act.get_json()['activity']['id']}", headers=h))
        ok(client.patch("/api/organization", json={"recording_retention_days": 5}, headers=h))
        ok(client.post("/api/recordings/purge", headers=h))
        ok(client.post(f"/api/sessions/{sid}/end", headers=h))
    finally:
        request_finished.disconnect(_record, app)

    missing = set(ROUTES) - hits
    assert not missing, f"routes without a successful call: {sorted(missing)}"


def test_instructor_role_and_org_scoping(client):
    """Non-admin instructors can't change org settings; objects are invisible across orgs."""
    from app.extensions import db
    from app.models import Instructor

    h, sess, clave, t1, _ = setup_class(client)
    other = setup_class.__globals__["auth_headers"](
        client, email="other@example.com", org="Other Org"
    )
    for method, url in [
        ("GET", f"/api/sessions/{sess['id']}"),
        ("PATCH", f"/api/teams/{t1['id']}"),
        ("POST", f"/api/sessions/{sess['id']}/rounds"),
        ("POST", f"/api/sessions/{sess['id']}/display-code"),
    ]:
        assert client.open(url, method=method, headers=other, json={"name": "x"}).status_code in (
            404,
            400,
        ), url

    inst = Instructor.query.filter_by(email="coach@example.com").one()
    inst.role = "instructor"
    db.session.commit()
    res = client.patch("/api/organization", json={"recording_retention_days": 3}, headers=h)
    assert res.status_code == 403
