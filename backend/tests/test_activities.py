from .helpers import auth_headers
from .test_rounds_api import play_turn, setup_class


def test_save_activity_from_session_and_list(client):
    h, sess, clave, t1, t2 = setup_class(client)
    rhythms = client.get("/api/rhythms?genre=hip-hop", headers=h).get_json()["rhythms"]
    play_turn(client, h, sess, clave, t1)
    play_turn(client, h, sess, rhythms[0], t2)
    play_turn(client, h, sess, clave, t2)
    res = client.post(
        "/api/activities", json={"name": "Tuesday set", "from_session_id": sess["id"]}, headers=h
    )
    assert res.status_code == 201
    act = res.get_json()["activity"]
    assert act["rhythm_ids"] == [clave["id"], rhythms[0]["id"]]
    assert [r["title"] for r in act["rhythms"]] == [clave["title"], rhythms[0]["title"]]

    manual = client.post(
        "/api/activities", json={"name": "Warm-up", "rhythm_ids": [rhythms[1]["id"]]}, headers=h
    ).get_json()["activity"]
    listed = client.get("/api/activities", headers=h).get_json()["activities"]
    assert [a["name"] for a in listed] == ["Warm-up", "Tuesday set"]

    other = auth_headers(client, email="z@example.com")
    assert client.get("/api/activities", headers=other).get_json()["activities"] == []
    assert client.delete(f"/api/activities/{manual['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/activities/{manual['id']}", headers=h).get_json()["deleted"]


def test_activity_validation(client):
    h, sess, *_ = setup_class(client)
    assert (
        client.post(
            "/api/activities", json={"name": "Empty", "from_session_id": sess["id"]}, headers=h
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/activities", json={"name": "X", "rhythm_ids": [99999]}, headers=h
        ).status_code
        == 400
    )
    assert client.post("/api/activities", json={"rhythm_ids": [1]}, headers=h).status_code == 400
    assert (
        client.post("/api/activities", json={"name": "X", "rhythm_ids": "1"}, headers=h).status_code
        == 400
    )
