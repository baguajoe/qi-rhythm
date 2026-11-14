import io
import time
from datetime import timedelta

import numpy as np
import soundfile as sf

from app.audio.synth import SynthOptions, render
from app.models import Round
from app.models.base import utcnow
from app.seed import seed_library

from .helpers import auth_headers


def wav(audio, sr):
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def setup_class(client, settings=None):
    seed_library()
    h = auth_headers(client)
    t1 = client.post(
        "/api/teams", json={"name": "Sunflowers", "color": "#b35900"}, headers=h
    ).get_json()["team"]
    t2 = client.post(
        "/api/teams", json={"name": "Blue Jays", "color": "#1f4e99"}, headers=h
    ).get_json()["team"]
    sess = client.post("/api/sessions", json={"settings": settings or {}}, headers=h).get_json()[
        "session"
    ]
    clave = next(
        r
        for r in client.get("/api/rhythms?genre=latin", headers=h).get_json()["rhythms"]
        if r["slug"] == "latin-son-clave-32"
    )
    return h, sess, clave, t1, t2


def play_turn(client, h, sess, rhythm, team, **synth):
    rnd = client.post(
        f"/api/sessions/{sess['id']}/rounds",
        json={"rhythm_id": rhythm["id"], "team_id": team["id"]},
        headers=h,
    ).get_json()["round"]
    assert (
        client.patch(
            f"/api/rounds/{rnd['id']}", json={"status": "playing_reference"}, headers=h
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/rounds/{rnd['id']}", json={"status": "recording"}, headers=h
        ).status_code
        == 200
    )
    pattern = rnd["reference"]["pattern"]
    s = render(pattern, SynthOptions(bpm=rnd["tempo_bpm_used"], lead_in_s=0.37, **synth))
    data = {
        "audio": (io.BytesIO(wav(s.audio, s.sr)), "take.wav"),
        "countin_start_s": str(s.countin_start_s),
    }
    t0 = time.perf_counter()
    res = client.post(
        f"/api/rounds/{rnd['id']}/recording",
        data=data,
        headers=h,
        content_type="multipart/form-data",
    )
    return res, rnd, time.perf_counter() - t0


def test_full_round_loop_two_teams(client):
    h, sess, clave, t1, t2 = setup_class(client)
    res, rnd, elapsed = play_turn(client, h, sess, clave, t1, jitter_ms=5, count_in_clicks=True)
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["round"]["status"] == "scored"
    assert body["score"]["machine"]["total"] >= 95
    assert body["score"]["needs_review"] is False
    assert body["round"]["capture"]["count_in_beats"] == 4
    assert elapsed < 3.0

    res2, _, _ = play_turn(client, h, sess, clave, t2, miss_indices=[1, 3])
    assert res2.get_json()["score"]["machine"]["pattern_accuracy"] < 85

    full = client.get(f"/api/sessions/{sess['id']}", headers=h).get_json()
    board = full["scoreboard"]["teams"]
    assert [row["team"]["name"] for row in board] == ["Sunflowers", "Blue Jays"]
    assert board[0]["turns"] == 1
    assert len(full["rounds"]) == 2

    score = client.get(f"/api/rounds/{rnd['id']}/score", headers=h).get_json()["score"]
    assert score["alignment"]["matched"]


def test_tempo_and_preset_come_from_session(client):
    h, sess, clave, t1, _ = setup_class(
        client, {"tempo_multiplier": 0.8, "tolerance_preset": "standard"}
    )
    rnd = client.post(
        f"/api/sessions/{sess['id']}/rounds",
        json={"rhythm_id": clave["id"], "team_id": t1["id"]},
        headers=h,
    ).get_json()["round"]
    assert rnd["tempo_bpm_used"] == round(clave["bpm"] * 0.8, 2)
    assert rnd["tolerance_preset"] == "standard"


def test_noisy_take_needs_review_and_override(client):
    h, sess, clave, t1, _ = setup_class(client)
    res, rnd, _ = play_turn(client, h, sess, clave, t1, noise_level=0.15, rumble_level=0.08)
    score = res.get_json()["score"]
    assert score["needs_review"] is True and score["review_reasons"]
    machine_total = score["machine"]["total"]

    res = client.post(
        f"/api/scores/{score['id']}/override",
        json={"pattern_accuracy": 90, "reason": "Heard them clearly"},
        headers=h,
    )
    body = res.get_json()
    assert body["round"]["status"] == "overridden"
    assert body["score"]["machine"]["total"] == machine_total  # original kept
    assert body["score"]["effective"]["pattern_accuracy"] == 90
    assert body["score"]["is_override"] and body["score"]["confirmed"]

    res = client.post(f"/api/scores/{score['id']}/override", json={"total": 88}, headers=h)
    assert res.get_json()["score"]["effective"]["total"] == 88
    teams = client.get("/api/teams", headers=h).get_json()["teams"]
    assert next(t for t in teams if t["id"] == t1["id"])["total_points"] == 88

    assert (
        client.post(
            f"/api/scores/{score['id']}/override", json={"total": 150}, headers=h
        ).status_code
        == 400
    )
    assert client.post(f"/api/scores/{score['id']}/override", json={}, headers=h).status_code == 400


def test_confirm_score(client):
    h, sess, clave, t1, _ = setup_class(client)
    res, _, _ = play_turn(client, h, sess, clave, t1)
    sid = res.get_json()["score"]["id"]
    assert client.post(f"/api/scores/{sid}/confirm", headers=h).get_json()["score"]["confirmed"]


def test_silence_scores_zero(client):
    h, sess, clave, t1, _ = setup_class(client)
    res, _, _ = play_turn(client, h, sess, clave, t1, hit_level=0.0)
    score = res.get_json()["score"]
    assert score["machine"]["total"] == 0 and score["needs_review"]


def test_round_guards(client):
    h, sess, clave, t1, _ = setup_class(client)
    res, rnd, _ = play_turn(client, h, sess, clave, t1)
    # cannot re-upload a scored turn or move it back to recording
    again = client.post(
        f"/api/rounds/{rnd['id']}/recording",
        data={"audio": (io.BytesIO(b"x" * 2000), "a.wav"), "countin_start_s": "0.5"},
        headers=h,
        content_type="multipart/form-data",
    )
    assert again.status_code == 409
    assert (
        client.patch(
            f"/api/rounds/{rnd['id']}", json={"status": "recording"}, headers=h
        ).status_code
        == 409
    )
    # bad uploads
    rnd2 = client.post(
        f"/api/sessions/{sess['id']}/rounds",
        json={"rhythm_id": clave["id"], "team_id": t1["id"]},
        headers=h,
    ).get_json()["round"]
    bad = client.post(
        f"/api/rounds/{rnd2['id']}/recording",
        data={"audio": (io.BytesIO(b"x" * 2000), "a.wav")},
        headers=h,
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    garbage = client.post(
        f"/api/rounds/{rnd2['id']}/recording",
        data={"audio": (io.BytesIO(b"x" * 2000), "a.wav"), "countin_start_s": "0.5"},
        headers=h,
        content_type="multipart/form-data",
    )
    assert garbage.status_code == 422
    assert (
        client.get(f"/api/sessions/{sess['id']}", headers=h).get_json()["rounds"][-1]["status"]
        == "failed"
    )
    # other org cannot see the round
    other = auth_headers(client, email="x@example.com")
    assert client.get(f"/api/rounds/{rnd['id']}/score", headers=other).status_code == 404


def test_end_session_blocks_new_rounds(client):
    h, sess, clave, t1, _ = setup_class(client)
    client.post(f"/api/sessions/{sess['id']}/end", headers=h)
    res = client.post(
        f"/api/sessions/{sess['id']}/rounds",
        json={"rhythm_id": clave["id"], "team_id": t1["id"]},
        headers=h,
    )
    assert res.status_code == 409


def test_session_settings_validation(client):
    h, sess, *_ = setup_class(client)
    ok = client.patch(
        f"/api/sessions/{sess['id']}",
        json={"settings": {"tolerance_preset": "challenge", "cooperative_mode": True}},
        headers=h,
    )
    assert ok.get_json()["session"]["settings"]["tolerance_preset"] == "challenge"
    assert ok.get_json()["scoreboard"]["cooperative"] is True
    for bad in ({"tolerance_preset": "extreme"}, {"tempo_multiplier": 2}, {"nope": 1}):
        assert (
            client.patch(
                f"/api/sessions/{sess['id']}", json={"settings": bad}, headers=h
            ).status_code
            == 400
        )


def test_calibration_profile_applied(client, db):
    h, _, clave, t1, _ = setup_class(client)
    client.post(
        "/api/calibration", json={"device_label": "Room", "latency_offset_ms": 140}, headers=h
    )
    sess = client.post("/api/sessions", json={}, headers=h).get_json()
    assert sess["calibration"]["latency_offset_ms"] == 140
    res, rnd, _ = play_turn(client, h, sess["session"], clave, t1, latency_ms=140, jitter_ms=3)
    assert res.get_json()["score"]["machine"]["total"] >= 95
    assert db.session.get(Round, rnd["id"]).latency_ms_used == 140


def test_recordings_stored_and_purged(client, db, app):
    h, sess, clave, t1, _ = setup_class(client)
    res, rnd, _ = play_turn(client, h, sess, clave, t1)
    r = db.session.get(Round, rnd["id"])
    from app.services.storage import get_storage

    assert get_storage().get(r.recording_key)[:4] == b"RIFF"
    # retention purge leaves fresh recordings alone, removes old ones
    from app.services.game import purge_recordings

    assert purge_recordings(older_than_days=-1) == 0
    r.created_at = utcnow() - timedelta(days=8)
    db.session.commit()
    assert purge_recordings(older_than_days=-1) == 1
    assert db.session.get(Round, rnd["id"]).recording_deleted_at is not None

    play_turn(client, h, sess, clave, t1)
    assert client.post("/api/recordings/purge", headers=h).get_json()["deleted"] == 1
    assert (
        client.get(f"/api/sessions/{sess['id']}", headers=h).get_json()["rounds"][-1][
            "has_recording"
        ]
        is False
    )


def test_org_retention_setting(client):
    h = auth_headers(client)
    res = client.patch("/api/organization", json={"recording_retention_days": 3}, headers=h)
    assert res.get_json()["organization"]["recording_retention_days"] == 3
    assert (
        client.patch(
            "/api/organization", json={"recording_retention_days": 400}, headers=h
        ).status_code
        == 400
    )
    assert np  # numpy import used by synth fixtures
