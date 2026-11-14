import numpy as np
import pytest

from app.audio.patterns import parse_events
from app.audio.scoring import analyze_take
from app.audio.synth import SynthOptions, render
from app.models import (
    ClassSession,
    Genre,
    Instructor,
    Organization,
    Participant,
    Rhythm,
    Round,
    Score,
    Team,
)
from app.seed import seed_demo, seed_library
from app.seed.library import GENRES

ALL_RHYTHMS = [(g["slug"], r) for g in GENRES for r in g["rhythms"]]


# ---------------------------------------------------------------- library content


@pytest.mark.parametrize("genre,r", ALL_RHYTHMS, ids=[r["slug"] for _, r in ALL_RHYTHMS])
def test_library_rhythm_is_well_formed(genre, r):
    events = parse_events(r["pattern"])
    beats = np.array([e.beat for e in events])
    assert len(set(np.round(beats, 4))) == len(beats), "no two events may share a beat"
    assert beats.max() < r["length_beats"]
    assert r["pattern"]["length_beats"] == r["length_beats"]
    assert r["difficulty"] in ("beginner", "intermediate", "advanced")
    assert r["source"] == "original" and r["license_notes"]
    # Minimum gap must exceed the onset detector's 70 ms min gap at 120% tempo.
    min_gap_s = np.diff(beats).min() * 60 / (r["bpm"] * 1.2) if len(beats) > 1 else 1
    assert min_gap_s > 0.1


@pytest.mark.parametrize("genre,r", ALL_RHYTHMS, ids=[r["slug"] for _, r in ALL_RHYTHMS])
def test_library_rhythm_perfect_take_scores_95(genre, r):
    pattern = r["pattern"]
    s = render(
        pattern,
        SynthOptions(
            bpm=r["bpm"], jitter_ms=5, count_in_clicks=True, noise_level=0.003, rumble_level=0.02
        ),
    )
    res = analyze_take(s.audio, pattern, sr=s.sr, bpm=r["bpm"], countin_start_s=s.countin_start_s)
    assert res.total >= 95, res.to_dict()["alignment"]


def test_library_shape():
    assert len(GENRES) == 7
    for g in GENRES:
        assert g["cultural_notes"].count(".") >= 2
        diffs = [r["difficulty"] for r in g["rhythms"]]
        assert diffs.count("beginner") >= 2
    slugs = [r["slug"] for _, r in ALL_RHYTHMS]
    assert len(slugs) == len(set(slugs))
    assert any("clave" in s for s in slugs)


# ---------------------------------------------------------------- seeding & models


def test_seed_is_idempotent(db):
    assert seed_library() == (7, len(ALL_RHYTHMS))
    seed_library()
    assert Genre.query.count() == 7
    assert Rhythm.query.count() == len(ALL_RHYTHMS)
    clave = Rhythm.query.filter_by(slug="latin-son-clave-32").one()
    assert clave.genre.slug == "latin"
    assert clave.engine_pattern["length_beats"] == 8


def test_seed_demo(db):
    inst = seed_demo()
    assert inst.check_password("rhythm-demo-123")
    assert seed_demo().id == inst.id
    assert Team.query.count() == 2


def test_participant_holds_alias_only():
    cols = {c.name for c in Participant.__table__.columns}
    assert cols == {"id", "team_id", "alias", "created_at"}


def test_score_override_keeps_machine_score(db):
    seed_library()
    org = Organization(name="Org", type="senior_center")
    db.session.add(org)
    db.session.flush()
    inst = Instructor(organization_id=org.id, display_name="I", email="i@example.com")
    inst.set_password("x" * 10)
    team = Team(organization_id=org.id, name="Reds", color="#aa0000")
    db.session.add_all([inst, team])
    db.session.flush()
    sess = ClassSession(organization_id=org.id, instructor_id=inst.id)
    db.session.add(sess)
    db.session.flush()
    rnd = Round(
        session_id=sess.id, rhythm_id=Rhythm.query.first().id, team_id=team.id, tempo_bpm_used=90
    )
    db.session.add(rnd)
    db.session.flush()
    sc = Score(
        round_id=rnd.id,
        pattern_accuracy=80,
        timing_accuracy=70,
        tempo_consistency=60,
        completion=100,
        total=77.5,
        confidence=0.4,
        needs_review=True,
    )
    db.session.add(sc)
    db.session.commit()
    assert sc.effective_total == 77.5
    sc.is_override = True
    sc.override_values = {"total": 90}
    db.session.commit()
    assert sc.effective_total == 90 and sc.machine["total"] == 77.5
    assert rnd.to_dict()["game_mode"] == "rhythm_recall"
    assert sess.to_dict()["settings"]["tolerance_preset"] == "gentle"
