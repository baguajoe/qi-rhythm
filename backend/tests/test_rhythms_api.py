from app.seed import seed_library

from .helpers import auth_headers


def test_genres_and_rhythm_filters(client, db):
    seed_library()
    h = auth_headers(client)
    genres = client.get("/api/genres", headers=h).get_json()["genres"]
    assert len(genres) == 7
    latin = next(g for g in genres if g["slug"] == "latin")
    assert latin["rhythm_count"] >= 5 and latin["cultural_notes"]

    rs = client.get("/api/rhythms?genre=latin&difficulty=beginner", headers=h).get_json()["rhythms"]
    assert rs and all(r["genre_slug"] == "latin" and r["difficulty"] == "beginner" for r in rs)
    assert any(r["slug"] == "latin-son-clave-32" for r in rs)

    all_rs = client.get("/api/rhythms", headers=h).get_json()["rhythms"]
    assert len(all_rs) == 36
    by_id = client.get(f"/api/rhythms/{rs[0]['id']}", headers=h).get_json()
    assert by_id["rhythm"]["pattern"]["events"] and by_id["genre"]["slug"] == "latin"

    assert client.get("/api/rhythms?difficulty=expert", headers=h).status_code == 400
    assert client.get("/api/rhythms/9999", headers=h).status_code == 404
    assert client.get("/api/rhythms").status_code == 401
