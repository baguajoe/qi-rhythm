"""Backing tracks: admin upload/validation, licensing gate, music level measurement, scoring."""

import io
from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio.synth import DEFAULT_BED, SynthOptions, _render_bed, render
from app.extensions import db as _db
from app.models import BackingTrack, Instructor, MusicBleedProfile

from .helpers import register
from .test_rounds_api import setup_class

BED_LEVEL, PAD_LEVEL = 0.3, 0.02


def loop_wav(seconds, sr=44100, subtype="PCM_24", channels=2, fmt="WAV"):
    """A Cubase-style groove loop (kick/snare/hats) of exactly ``seconds``."""
    buf = np.zeros(int(round(seconds * sr)))
    opts = SynthOptions(sr=sr, bpm=90, bed_level=0.5)
    _render_bed(buf, 0.0, 60 / 90, opts, np.random.default_rng(0))
    audio = np.stack([buf] * channels, axis=1) if channels > 1 else buf
    out = io.BytesIO()
    sf.write(out, np.clip(audio, -1, 1), sr, format=fmt, subtype=subtype)
    return out.getvalue()


ONE_BAR_90 = 4 * 60 / 90  # 2.6667 s


def upload(client, h, rhythm_id, data=None, version="bed", **fields):
    form = {
        "audio": (io.BytesIO(data if data is not None else loop_wav(ONE_BAR_90)), "groove.wav"),
        "version": version,
        "bpm": "90",
        "bars": "1",
        "notes": "Cubase export, dry",
        **fields,
    }
    return client.post(
        f"/api/rhythms/{rhythm_id}/backing-tracks",
        data=form,
        headers=h,
        content_type="multipart/form-data",
    )


LICENSED = {"source": "original", "license_notes": "Recorded by the project owner, 2026."}


# ---------------------------------------------------------------- upload + validation


def test_upload_valid_wav_reports_duration_and_needs_license(client):
    h, _, clave, _, _ = setup_class(client)
    res = upload(client, h, clave["id"])
    assert res.status_code == 201, res.get_json()
    t = res.get_json()["track"]
    assert t["version"] == "bed" and t["sample_rate"] == 44100 and t["channels"] == 2
    assert abs(t["duration_s"] - ONE_BAR_90) < 0.001
    assert abs(t["expected_duration_s"] - ONE_BAR_90) < 0.001
    assert t["loop_beats"] == 4
    assert t["usable"] is False
    assert t["warnings"] == [
        "Add the source and license notes before this track can be used in a class."
    ]
    assert t["notes"] == "Cubase export, dry"


def test_48k_wav_with_license_is_usable(client):
    h, _, clave, _, _ = setup_class(client)
    res = upload(client, h, clave["id"], data=loop_wav(ONE_BAR_90, sr=48000), **LICENSED)
    t = res.get_json()["track"]
    assert res.status_code == 201 and t["usable"] is True and t["warnings"] == []


def test_duration_mismatch_warns(client):
    h, _, clave, _, _ = setup_class(client)
    t = upload(client, h, clave["id"], data=loop_wav(3.2), **LICENSED).get_json()["track"]
    assert len(t["warnings"]) == 1
    assert "3.20 s long" in t["warnings"][0] and "2.67 s" in t["warnings"][0]
    # Telling it the loop is 2 bars at 150 BPM (= 3.2 s) clears the warning.
    t = client.patch(
        f"/api/backing-tracks/{t['id']}", json={"bpm": 150, "bars": 2}, headers=h
    ).get_json()["track"]
    assert not any("long" in w for w in t["warnings"])
    assert any("sped up or slowed down" in w for w in t["warnings"])


def test_loop_length_that_does_not_fit_pattern_warns(client):
    h, _, clave, _, _ = setup_class(client)  # clave is 8 beats
    t = upload(client, h, clave["id"], data=loop_wav(3 * 60 / 90), bars="1", **LICENSED)
    t = client.patch(
        f"/api/backing-tracks/{t.get_json()['track']['id']}", json={"bars": 3}, headers=h
    ).get_json()["track"]
    assert any("won't line up" in w for w in t["warnings"])


def test_rejects_wrong_format_and_sample_rate(client):
    h, _, clave, _, _ = setup_class(client)
    res = upload(client, h, clave["id"], data=loop_wav(ONE_BAR_90, sr=22050))
    assert res.status_code == 400 and "44.1 kHz or 48 kHz" in res.get_json()["error"]
    flac = loop_wav(ONE_BAR_90, fmt="FLAC", subtype="PCM_16")
    res = upload(client, h, clave["id"], data=flac)
    assert res.status_code == 400 and "not WAV" in res.get_json()["error"]
    res = upload(client, h, clave["id"], data=b"ID3 this is an mp3" * 100)
    assert res.status_code == 400 and "isn't a WAV" in res.get_json()["error"]
    res = upload(client, h, clave["id"], data=b"")
    assert res.status_code == 400


def test_rejects_bad_metadata(client):
    h, _, clave, _, _ = setup_class(client)
    assert upload(client, h, clave["id"], version="loud").status_code == 400
    assert upload(client, h, clave["id"], bpm="fast").status_code == 400
    assert upload(client, h, clave["id"], bars="0").status_code == 400
    assert upload(client, h, clave["id"], source="found online").status_code == 400
    assert upload(client, h, 99999).status_code == 404


def test_too_large_upload_has_plain_message(client, app):
    h, _, clave, _, _ = setup_class(client)
    app.config["MAX_CONTENT_LENGTH"] = 200_000
    try:
        res = upload(client, h, clave["id"])
    finally:
        app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    assert res.status_code == 413 and "too big" in res.get_json()["error"]


def test_replacing_a_version_deletes_old_file_and_measurements(client, app):
    h, _, clave, _, _ = setup_class(client)
    first = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    old_key = _db.session.get(BackingTrack, first["id"]).storage_key
    _db.session.add(
        MusicBleedProfile(
            organization_id=1, backing_track_id=first["id"], profile={"floor_db": -40}
        )
    )
    _db.session.commit()
    second = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    assert second["id"] == first["id"]
    assert not (Path(app.config["LOCAL_STORAGE_DIR"]) / old_key).exists()
    assert MusicBleedProfile.query.count() == 0
    assert upload(client, h, clave["id"], version="full").status_code == 201
    tracks = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=h).get_json()
    assert sorted(t["version"] for t in tracks["tracks"]) == ["bed", "full"]


def test_license_gate_and_audio_access(client, app):
    h, _, clave, _, _ = setup_class(client)
    t = upload(client, h, clave["id"]).get_json()["track"]
    # Admin can preview before licensing; a regular instructor can't.
    assert client.get(t["audio_path"], headers=h).status_code == 200
    inst = Instructor(
        organization_id=1, display_name="Helper", email="helper@example.com", role="instructor"
    )
    inst.set_password("helper-password")
    _db.session.add(inst)
    _db.session.commit()
    tok = client.post(
        "/api/auth/login", json={"email": "helper@example.com", "password": "helper-password"}
    ).get_json()["access_token"]
    helper = {"Authorization": f"Bearer {tok}"}
    assert client.get(t["audio_path"], headers=helper).status_code == 403
    # Regular instructors can't upload, edit or delete.
    assert upload(client, helper, clave["id"]).status_code == 403
    assert (
        client.patch(f"/api/backing-tracks/{t['id']}", json=LICENSED, headers=helper).status_code
        == 403
    )
    assert client.delete(f"/api/backing-tracks/{t['id']}", headers=helper).status_code == 403

    # Source alone isn't enough; license notes are required too.
    t2 = client.patch(
        f"/api/backing-tracks/{t['id']}", json={"source": "licensed"}, headers=h
    ).get_json()["track"]
    assert t2["usable"] is False
    t2 = client.patch(
        f"/api/backing-tracks/{t['id']}", json={"license_notes": "  "}, headers=h
    ).get_json()["track"]
    assert t2["usable"] is False
    t2 = client.patch(
        f"/api/backing-tracks/{t['id']}",
        json={"license_notes": "Licence #123 from Loops Inc, perpetual, live use OK"},
        headers=h,
    ).get_json()["track"]
    assert t2["usable"] is True
    res = client.get(t["audio_path"], headers=helper)
    assert res.status_code == 200 and res.mimetype == "audio/wav"
    assert sf.info(io.BytesIO(res.data)).samplerate == 44100


def test_other_organizations_cannot_see_tracks(client):
    h, _, clave, _, _ = setup_class(client)
    t = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    other = {"Authorization": f"Bearer {register(client, email='x@example.com')['access_token']}"}
    assert client.get("/api/backing-tracks", headers=other).get_json()["tracks"] == []
    assert client.get(t["audio_path"], headers=other).status_code == 404
    assert client.patch(f"/api/backing-tracks/{t['id']}", json={}, headers=other).status_code == 404
    assert client.delete(f"/api/backing-tracks/{t['id']}", headers=other).status_code == 404


def test_delete_track(client, app):
    h, _, clave, _, _ = setup_class(client)
    t = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    key = _db.session.get(BackingTrack, t["id"]).storage_key
    assert client.delete(f"/api/backing-tracks/{t['id']}", headers=h).status_code == 200
    assert not (Path(app.config["LOCAL_STORAGE_DIR"]) / key).exists()
    assert client.get("/api/backing-tracks", headers=h).get_json()["tracks"] == []


# ---------------------------------------------------------------- class flow


def new_round(client, h, sess, rhythm, team):
    return client.post(
        f"/api/sessions/{sess['id']}/rounds",
        json={"rhythm_id": rhythm["id"], "team_id": team["id"]},
        headers=h,
    ).get_json()["round"]


def test_reference_lists_usable_tracks_unless_music_is_off(client):
    h, sess, clave, t1, _ = setup_class(client)
    assert new_round(client, h, sess, clave, t1)["reference"]["music"] is None
    bed = upload(client, h, clave["id"]).get_json()["track"]
    assert new_round(client, h, sess, clave, t1)["reference"]["music"] is None  # unlicensed
    client.patch(f"/api/backing-tracks/{bed['id']}", json=LICENSED, headers=h)
    music = new_round(client, h, sess, clave, t1)["reference"]["music"]
    assert music["full"] is None
    assert music["bed"]["id"] == bed["id"] and music["bed"]["loop_beats"] == 4
    assert abs(music["bed"]["loop_seconds"] - ONE_BAR_90) < 1e-3
    client.patch(f"/api/sessions/{sess['id']}", json={"settings": {"music_on": False}}, headers=h)
    assert new_round(client, h, sess, clave, t1)["reference"]["music"] is None


def test_music_settings_validation(client):
    h, sess, *_ = setup_class(client)
    res = client.patch(
        f"/api/sessions/{sess['id']}", json={"settings": {"music_volume": 1.5}}, headers=h
    )
    assert res.status_code == 400
    s = client.patch(
        f"/api/sessions/{sess['id']}",
        json={"settings": {"music_volume": 0.4, "volume": 0.9}},
        headers=h,
    ).get_json()["session"]["settings"]
    assert s["music_volume"] == 0.4 and s["volume"] == 0.9 and s["music_on"] is True


def room_take(pattern, bpm, **kw):
    return render(
        pattern,
        SynthOptions(
            bpm=bpm,
            lead_in_s=0.37,
            latency_ms=0.0,
            bed=DEFAULT_BED,
            bed_level=BED_LEVEL,
            bed_pad_level=PAD_LEVEL,
            noise_level=0.003,
            count_in_clicks=True,
            click_level=0.15,
            **kw,
        ),
    )


def measure_music(client, h, sess, track_id, bpm=90, volume=0.6):
    s = room_take({"events": [{"beat": 0, "voice": "clap"}]}, bpm, team_silent=True, seed=7)
    return client.post(
        f"/api/backing-tracks/{track_id}/bleed",
        data={
            "audio": (io.BytesIO(wav(s.audio, s.sr)), "music.wav"),
            "bpm": str(bpm),
            "music_start_s": str(s.bed_start_s),
            "music_volume": str(volume),
            "session_id": str(sess["id"]),
        },
        headers=h,
        content_type="multipart/form-data",
    )


def wav(audio, sr):
    out = io.BytesIO()
    sf.write(out, audio, sr, format="WAV", subtype="PCM_16")
    return out.getvalue()


def music_turn(client, h, sess, rhythm, team, track_id, **synth):
    rnd = new_round(client, h, sess, rhythm, team)
    client.patch(f"/api/rounds/{rnd['id']}", json={"status": "playing_reference"}, headers=h)
    client.patch(f"/api/rounds/{rnd['id']}", json={"status": "recording"}, headers=h)
    s = room_take(rnd["reference"]["pattern"], rnd["tempo_bpm_used"], jitter_ms=8, **synth)
    form = {
        "audio": (io.BytesIO(wav(s.audio, s.sr)), "take.wav"),
        "countin_start_s": str(s.countin_start_s),
    }
    if track_id is not None:
        form |= {
            "backing_track_id": str(track_id),
            "music_start_s": str(s.bed_start_s),
            "music_volume": "0.6",
        }
    return client.post(
        f"/api/rounds/{rnd['id']}/recording",
        data=form,
        headers=h,
        content_type="multipart/form-data",
    )


def test_measure_music_level_then_team_turn_over_the_bed(client):
    h, sess, clave, t1, _ = setup_class(client)
    bed = upload(client, h, clave["id"], **LICENSED).get_json()["track"]

    # Before measuring: the turn still scores, but the instructor is told to measure.
    res = music_turn(client, h, sess, clave, t1, bed["id"])
    assert res.status_code == 201, res.get_json()
    score = res.get_json()["score"]
    assert score["needs_review"] is True
    assert any("Measure music level" in r for r in score["review_reasons"])

    res = measure_music(client, h, sess, bed["id"])
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["tone"] == "success" and body["music_level"]["transients_per_loop"] == 8
    listed = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=h).get_json()
    assert listed["tracks"][0]["music_level"]["music_volume"] == 0.6

    res = music_turn(client, h, sess, clave, t1, bed["id"], seed=3)
    body = res.get_json()
    assert body["round"]["backing_track_id"] == bed["id"]
    assert body["round"]["music_volume_used"] == 0.6
    assert body["score"]["needs_review"] is False, body["score"]["review_reasons"]
    assert body["score"]["machine"]["total"] >= 95
    assert len(body["score"]["alignment"]["matched"]) == 5

    # Missed hits still cost points with the music playing.
    missed = music_turn(client, h, sess, clave, t1, bed["id"], miss_indices=[1, 3]).get_json()
    assert len(missed["score"]["alignment"]["missed"]) == 2


def test_turn_without_bleed_info_counts_music_as_hits(client):
    """Same take, analysed as if no music had played: the bed's drums become extra hits."""
    h, sess, clave, t1, _ = setup_class(client)
    bed = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    measure_music(client, h, sess, bed["id"])
    with_info = music_turn(client, h, sess, clave, t1, bed["id"], seed=4).get_json()
    without = music_turn(client, h, sess, clave, t1, None, seed=4).get_json()
    assert len(with_info["score"]["alignment"]["extras"]) == 0
    assert len(without["score"]["alignment"]["extras"]) > 0
    assert without["round"]["backing_track_id"] is None


def test_measure_and_upload_guards(client):
    h, sess, clave, t1, _ = setup_class(client)
    full = upload(client, h, clave["id"], version="full", **LICENSED).get_json()["track"]
    bed = upload(client, h, clave["id"]).get_json()["track"]  # not licensed
    assert measure_music(client, h, sess, full["id"]).status_code == 400
    assert measure_music(client, h, sess, bed["id"]).status_code == 400
    res = music_turn(client, h, sess, clave, t1, full["id"])
    assert res.status_code == 400 and "can't be used" in res.get_json()["error"]
    res = music_turn(client, h, sess, clave, t1, bed["id"])
    assert res.status_code == 400


# ---------------------------------------------------------------- Qi Rhythm Library


def make_superadmin(client, email="team@eyeforge.example"):
    """The Eye Forge Studios account. Super-admin is granted only via the CLI (as here)."""
    tok = register(client, email=email, org="Eye Forge Studios")["access_token"]
    inst = Instructor.query.filter_by(email=email).one()
    inst.role = "superadmin"
    _db.session.commit()
    return {"Authorization": f"Bearer {tok}"}


def test_only_superadmins_can_add_to_the_library(client):
    h, _, clave, _, _ = setup_class(client)  # an ordinary org admin
    res = upload(client, h, clave["id"], scope="library", **LICENSED)
    assert res.status_code == 403 and "Eye Forge Studios" in res.get_json()["error"]
    assert upload(client, h, clave["id"], scope="everyone").status_code == 400
    sup = make_superadmin(client)
    res = upload(client, sup, clave["id"], scope="library", **LICENSED)
    assert res.status_code == 201, res.get_json()
    t = res.get_json()["track"]
    assert t["scope"] == "library" and t["badge"] == "Qi Rhythm Original"
    assert _db.session.get(BackingTrack, t["id"]).organization_id is None
    assert _db.session.get(BackingTrack, t["id"]).storage_key.startswith("backing/library/")


def test_every_organization_gets_library_tracks_but_cannot_change_them(client):
    h, sess, clave, t1, _ = setup_class(client)
    sup = make_superadmin(client)
    lib = upload(client, sup, clave["id"], scope="library", **LICENSED).get_json()["track"]

    listing = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=h).get_json()
    (seen,) = listing["tracks"]
    assert seen["id"] == lib["id"] and seen["badge"] == "Qi Rhythm Original"
    assert seen["in_use"] is True and seen["can_edit"] is False
    assert listing["library"] == {
        "name": "Qi Rhythm Library",
        "owner": "Eye Forge Studios",
        "can_edit": False,
    }
    assert client.get(lib["audio_path"], headers=h).status_code == 200
    assert (
        client.patch(f"/api/backing-tracks/{lib['id']}", json={"bpm": 91}, headers=h).status_code
        == 403
    )
    assert client.delete(f"/api/backing-tracks/{lib['id']}", headers=h).status_code == 403
    music = new_round(client, h, sess, clave, t1)["reference"]["music"]
    assert music["bed"]["id"] == lib["id"] and music["bed"]["badge"] == "Qi Rhythm Original"

    # The super-admin can edit and delete it.
    res = client.patch(f"/api/backing-tracks/{lib['id']}", json={"notes": "v2"}, headers=sup)
    assert res.status_code == 200 and res.get_json()["track"]["can_edit"] is True
    assert client.delete(f"/api/backing-tracks/{lib['id']}", headers=sup).status_code == 200
    assert client.get("/api/backing-tracks", headers=h).get_json()["tracks"] == []


def test_unlicensed_library_tracks_are_hidden_from_classes(client):
    h, sess, clave, t1, _ = setup_class(client)
    sup = make_superadmin(client)
    lib = upload(client, sup, clave["id"], scope="library").get_json()["track"]  # no license
    assert client.get(lib["audio_path"], headers=h).status_code == 403
    assert client.get(lib["audio_path"], headers=sup).status_code == 200
    assert new_round(client, h, sess, clave, t1)["reference"]["music"] is None


def test_an_organizations_own_loop_plays_instead_of_the_library_one(client):
    h, sess, clave, t1, _ = setup_class(client)
    sup = make_superadmin(client)
    lib_bed = upload(client, sup, clave["id"], scope="library", **LICENSED).get_json()["track"]
    lib_full = upload(
        client, sup, clave["id"], scope="library", version="full", **LICENSED
    ).get_json()["track"]
    own_bed = upload(client, h, clave["id"], **LICENSED).get_json()["track"]
    assert own_bed["scope"] == "organization" and own_bed["badge"] is None

    tracks = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=h).get_json()
    in_use = {t["id"]: t["in_use"] for t in tracks["tracks"]}
    assert in_use == {lib_bed["id"]: False, lib_full["id"]: True, own_bed["id"]: True}
    assert [t["scope"] for t in tracks["tracks"]][:2] == ["library", "library"]  # library first
    music = new_round(client, h, sess, clave, t1)["reference"]["music"]
    assert music["bed"]["id"] == own_bed["id"] and music["full"]["id"] == lib_full["id"]

    # The super-admin's own organization still sees the library loop for "bed".
    sup_view = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=sup).get_json()
    assert {t["id"] for t in sup_view["tracks"]} == {lib_bed["id"], lib_full["id"]}
    assert all(t["in_use"] for t in sup_view["tracks"])

    # Removing the org's own loop falls back to the library again.
    client.delete(f"/api/backing-tracks/{own_bed['id']}", headers=h)
    music = new_round(client, h, sess, clave, t1)["reference"]["music"]
    assert music["bed"]["id"] == lib_bed["id"]


def test_music_level_of_a_library_track_is_per_organization(client):
    h, sess, clave, t1, _ = setup_class(client)
    sup = make_superadmin(client)
    lib = upload(client, sup, clave["id"], scope="library", **LICENSED).get_json()["track"]
    assert measure_music(client, h, sess, lib["id"]).status_code == 201
    profile = MusicBleedProfile.query.one()
    assert profile.organization_id == 1  # the measuring org, not the library

    # This org's turn over the library groove uses its own measurement.
    body = music_turn(client, h, sess, clave, t1, lib["id"], seed=3).get_json()
    assert body["round"]["backing_track_id"] == lib["id"]
    assert body["score"]["needs_review"] is False
    assert body["score"]["machine"]["total"] >= 95

    # Another organization hasn't measured its room yet: its listing shows no music level.
    other = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=sup).get_json()
    assert other["tracks"][0]["music_level"] is None
    mine = client.get(f"/api/backing-tracks?rhythm_id={clave['id']}", headers=h).get_json()
    assert mine["tracks"][0]["music_level"] is not None


def test_superadmin_is_also_an_admin_of_its_own_organization(client):
    from app.seed import seed_library

    seed_library()
    sup = make_superadmin(client)
    res = client.patch("/api/organization", json={"recording_retention_days": 3}, headers=sup)
    assert res.status_code == 200
    rid = client.get("/api/rhythms", headers=sup).get_json()["rhythms"][0]["id"]
    assert upload(client, sup, rid, **LICENSED).get_json()["track"]["scope"] == "organization"


def test_set_role_cli(app, client):
    register(client, email="owner@eyeforge.example")
    runner = app.test_cli_runner()
    res = runner.invoke(args=["set-role", "Owner@EyeForge.example", "superadmin"])
    assert res.exit_code == 0 and "admin -> superadmin" in res.output
    assert Instructor.query.filter_by(email="owner@eyeforge.example").one().role == "superadmin"
    res = runner.invoke(args=["set-role", "nobody@example.com", "admin"])
    assert res.exit_code != 0 and "No instructor" in res.output
    res = runner.invoke(args=["set-role", "owner@eyeforge.example", "owner"])
    assert res.exit_code != 0
