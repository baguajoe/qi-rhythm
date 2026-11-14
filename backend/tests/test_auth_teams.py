from .helpers import auth_headers, register


def test_register_login_me(client):
    data = register(client)
    assert data["instructor"]["role"] == "admin"
    assert data["organization"]["recording_retention_days"] == 7
    res = client.post(
        "/api/auth/login", json={"email": "COACH@example.com", "password": "drumcircle1"}
    )
    assert res.status_code == 200
    token = res.get_json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.get_json()["instructor"]["email"] == "coach@example.com"


def test_register_validation(client):
    register(client)
    dup = client.post(
        "/api/auth/register",
        json={
            "organization_name": "X",
            "display_name": "Y",
            "email": "coach@example.com",
            "password": "drumcircle1",
        },
    )
    assert dup.status_code == 409
    short = client.post(
        "/api/auth/register",
        json={
            "organization_name": "X",
            "display_name": "Y",
            "email": "b@example.com",
            "password": "short",
        },
    )
    assert short.status_code == 400 and "10 characters" in short.get_json()["error"]
    bad = client.post(
        "/api/auth/register",
        json={"organization_name": "X", "display_name": "Y", "email": "nope", "password": "x" * 12},
    )
    assert bad.status_code == 400


def test_login_failure_is_plain_language(client):
    register(client)
    res = client.post("/api/auth/login", json={"email": "coach@example.com", "password": "wrong"})
    assert res.status_code == 401
    assert "don't match" in res.get_json()["error"]


def test_protected_routes_require_token(client):
    assert client.get("/api/teams").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_team_crud_and_participants(client):
    h = auth_headers(client)
    res = client.post(
        "/api/teams",
        json={"name": "Sunflowers", "color": "#B35900", "mascot_icon": "sun"},
        headers=h,
    )
    assert res.status_code == 201
    team = res.get_json()["team"]
    assert team["color"] == "#b35900" and team["participants"] == []

    res = client.patch(f"/api/teams/{team['id']}", json={"name": "Sunny Sunflowers"}, headers=h)
    assert res.get_json()["team"]["name"] == "Sunny Sunflowers"

    res = client.post(f"/api/teams/{team['id']}/participants", json={"alias": "Rosie"}, headers=h)
    assert res.status_code == 201
    pid = res.get_json()["participant"]["id"]
    assert [p["alias"] for p in res.get_json()["team"]["participants"]] == ["Rosie"]

    # privacy guard: no extra participant fields accepted
    res = client.post(
        f"/api/teams/{team['id']}/participants",
        json={"alias": "Al", "birthdate": "1940-01-01"},
        headers=h,
    )
    assert res.status_code == 400

    res = client.delete(f"/api/teams/{team['id']}/participants/{pid}", headers=h)
    assert res.get_json()["team"]["participants"] == []

    client.patch(f"/api/teams/{team['id']}", json={"is_active": False}, headers=h)
    assert client.get("/api/teams", headers=h).get_json()["teams"] == []
    assert len(client.get("/api/teams?include_inactive=1", headers=h).get_json()["teams"]) == 1


def test_team_validation(client):
    h = auth_headers(client)
    assert (
        client.post("/api/teams", json={"name": "", "color": "#000000"}, headers=h).status_code
        == 400
    )
    assert (
        client.post("/api/teams", json={"name": "A", "color": "red"}, headers=h).status_code == 400
    )
    assert (
        client.post(
            "/api/teams", json={"name": "A", "color": "#000000", "mascot_icon": "dragon"}, headers=h
        ).status_code
        == 400
    )


def test_teams_are_isolated_between_organizations(client):
    h1 = auth_headers(client, email="a@example.com")
    h2 = auth_headers(client, email="b@example.com", org="Other Place")
    team = client.post(
        "/api/teams", json={"name": "Mine", "color": "#1f4e99"}, headers=h1
    ).get_json()["team"]
    assert client.get(f"/api/teams/{team['id']}", headers=h2).status_code == 404
    assert (
        client.patch(f"/api/teams/{team['id']}", json={"name": "Stolen"}, headers=h2).status_code
        == 404
    )
    assert client.get("/api/teams", headers=h2).get_json()["teams"] == []
