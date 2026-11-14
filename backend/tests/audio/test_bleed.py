"""Backing-track bleed: a music bed with drums plays through the room speaker under the team."""

import numpy as np
import pytest

from app.audio.bleed import BleedProfile, bleed_mask, bleed_params, measure_bleed, volume_gain_db
from app.audio.onset import OnsetParams, estimate_bleed_shift
from app.audio.scoring import analyze_take
from app.audio.synth import DEFAULT_BED, SynthOptions, render

from .conftest import SON_CLAVE_32

BPM = 90.0
LATENCY = 60.0
ROOM = dict(bpm=BPM, latency_ms=LATENCY, noise_level=0.003, count_in_clicks=True, click_level=0.15)


def clave(voice):
    return {**SON_CLAVE_32, "events": [{**e, "voice": voice} for e in SON_CLAVE_32["events"]]}


def measure(pattern, bed_level, pad, volume=0.6, latency_ms=LATENCY):
    """'Measure music level': the bed alone through the speaker, nobody playing."""
    s = render(
        pattern,
        SynthOptions(**ROOM, bed_level=bed_level, bed_pad_level=pad, team_silent=True, seed=99),
    )
    return measure_bleed(
        s.audio,
        sr=s.sr,
        bpm=BPM,
        bed_start_s=s.bed_start_s,
        loop_beats=4,
        latency_ms=latency_ms,
        music_volume=volume,
    )


def team_take(
    pattern,
    profile,
    bed_level,
    pad,
    *,
    seed=1,
    with_bleed=True,
    volume=0.6,
    latency_ms=LATENCY,
    **kw,
):
    s = render(
        pattern,
        SynthOptions(**ROOM, bed_level=bed_level, bed_pad_level=pad, jitter_ms=15, seed=seed, **kw),
    )
    params = OnsetParams()
    if with_bleed:
        params = bleed_params(
            profile,
            params,
            bpm=BPM,
            bed_start_s=s.bed_start_s,
            duration_s=len(s.audio) / s.sr,
            latency_ms=latency_ms,
            music_volume=volume,
        )
    res = analyze_take(
        s.audio,
        pattern,
        sr=s.sr,
        bpm=BPM,
        countin_start_s=s.countin_start_s,
        latency_ms=latency_ms,
        onset_params=params,
    )
    return res, s


# ---------------------------------------------------------------- synth


def test_bed_loops_from_the_count_in_downbeat_and_team_silent_renders_no_hits():
    s = render(SON_CLAVE_32, SynthOptions(bpm=BPM, bed_level=0.3, team_silent=True, lead_in_s=0.5))
    assert s.hit_times == [] and s.bed_start_s == pytest.approx(0.5)
    spb = 60 / BPM
    kicks = [0.5 + (4 * k + b) * spb for k in range(3) for b in (0, 2)]
    for t in kicks:
        assert min(abs(np.array(s.bed_times) - t)) < 1e-9
    per_loop = len(DEFAULT_BED["events"])
    assert len(s.bed_times) >= 4 * per_loop  # count-in + 2 pattern bars + slack


def test_no_bed_by_default():
    s = render(SON_CLAVE_32, SynthOptions(bpm=BPM))
    assert s.bed_start_s is None and s.bed_times == []


# ---------------------------------------------------------------- measuring the bed


def grid_beats(prof):
    """Loop positions, with ones just before the loop end (slightly early beat 0) unwrapped."""
    return sorted(
        b - prof.loop_beats if b > prof.loop_beats - 0.25 else b
        for b in (t["beat"] for t in prof.transients)
    )


def test_measure_finds_every_bed_drum_on_the_beat_grid():
    prof = measure(SON_CLAVE_32, bed_level=0.3, pad=0.02)
    beats = grid_beats(prof)
    # kick/snare on every beat + hats on every eighth = 8 positions per 4-beat loop
    assert beats == pytest.approx([b / 2 for b in range(8)], abs=0.03)
    assert prof.loops_measured >= 4
    assert -60 < prof.floor_db < -20
    assert all(len(t["bands"]) == 5 for t in prof.transients)
    assert BleedProfile.from_dict(prof.to_dict()) == prof


def test_measured_positions_exclude_device_latency():
    a = measure(SON_CLAVE_32, 0.3, 0.02, latency_ms=LATENCY)
    b = measure(SON_CLAVE_32, 0.3, 0.02, latency_ms=0.0)  # latency left in the positions
    snare_a = next(x for x in grid_beats(a) if abs(x - 1) < 0.2)
    snare_b = next(x for x in grid_beats(b) if abs(x - 1) < 0.2)
    shift = (snare_b - snare_a) * 60 / BPM * 1000
    assert shift == pytest.approx(LATENCY, abs=8)


def test_silent_measurement_has_no_transients():
    s = render(SON_CLAVE_32, SynthOptions(bpm=BPM, team_silent=True, noise_level=0.002))
    prof = measure_bleed(s.audio, sr=s.sr, bpm=BPM, bed_start_s=0.5, loop_beats=4)
    assert prof.transients == []
    assert bleed_mask(prof, bpm=BPM, bed_start_s=0.5, duration_s=10) == []


def test_mask_follows_tempo_latency_and_volume():
    prof = BleedProfile(
        loop_beats=4,
        floor_db=-40,
        music_volume=0.5,
        bpm=90,
        transients=[{"beat": 0.0, "level_db": -20, "bands": [-30] * 5, "seen": 4}],
    )
    mask = bleed_mask(
        prof, bpm=120, bed_start_s=1.0, latency_ms=50, duration_s=7.0, music_volume=1.0
    )
    assert [t for t, _ in mask] == pytest.approx([1.05, 3.05, 5.05])  # one per 2 s loop @120
    assert mask[0][1][0] == pytest.approx(-30 + 20 * np.log10(2))
    assert volume_gain_db(0.5, 0.0) == -120.0


# ---------------------------------------------------------------- team claps over the bed


@pytest.mark.parametrize("bed_level,pad", [(0.15, 0.01), (0.3, 0.02), (0.5, 0.03)])
def test_claps_over_a_drum_bed_score_like_a_quiet_room(bed_level, pad):
    prof = measure(SON_CLAVE_32, bed_level, pad)
    res, _ = team_take(SON_CLAVE_32, prof, bed_level, pad)
    assert res.hits_detected == 5 and res.hits_matched == 5
    assert res.total >= 95 and not res.needs_review


def test_without_bleed_handling_the_bed_is_counted_as_hits():
    prof = measure(SON_CLAVE_32, 0.3, 0.02)
    raw, _ = team_take(SON_CLAVE_32, prof, 0.3, 0.02, with_bleed=False)
    handled, _ = team_take(SON_CLAVE_32, prof, 0.3, 0.02)
    assert raw.hits_detected > 5 and handled.hits_detected == 5
    assert handled.pattern_accuracy > raw.pattern_accuracy


def test_claps_landing_on_the_kick_and_hats_are_kept():
    # Every clave note lines up with a bed hat, and beats 0 and 6 with the kick.
    prof = measure(SON_CLAVE_32, 0.5, 0.03)
    res, s = team_take(SON_CLAVE_32, prof, 0.5, 0.03)
    found = np.array([o["time_s"] for o in res.detected_onsets])
    for t in s.hit_times:
        assert np.min(np.abs(found - t)) < 0.03


def test_missed_hits_are_still_missed_with_music_playing():
    prof = measure(SON_CLAVE_32, 0.3, 0.02)
    res, _ = team_take(SON_CLAVE_32, prof, 0.3, 0.02, miss_indices=[1, 3])
    assert res.hits_matched == 3 and res.hits_detected == 3
    assert res.pattern_accuracy < 90


@pytest.mark.parametrize("voice", ["high", "low", "shaker"])
def test_hand_drums_and_shakers_over_the_bed(voice):
    # (A shaker over LOUD hi-hats is the known weak case: same sound, same beat.)
    pattern = clave(voice)
    prof = measure(pattern, 0.3, 0.02)
    res, _ = team_take(pattern, prof, 0.3, 0.02, seed=2)
    assert res.hits_matched == 5 and res.total >= 95


def test_music_volume_changed_after_measuring():
    prof = measure(SON_CLAVE_32, 0.3, 0.02, volume=0.6)
    louder, _ = team_take(SON_CLAVE_32, prof, 0.45, 0.03, volume=0.9)  # slider 0.6 -> 0.9
    assert louder.hits_detected == 5 and louder.total >= 95


@pytest.mark.parametrize("err_ms", [-80, -25, 25, 80])
def test_latency_error_is_measured_from_the_bed_itself(err_ms):
    # The tap-test latency includes human reaction time; the bed's repeating drums reveal the
    # real offset, so even an 80 ms error leaves the masking intact.
    prof = measure(SON_CLAVE_32, 0.3, 0.02)
    res, _ = team_take(SON_CLAVE_32, prof, 0.3, 0.02, latency_ms=LATENCY + err_ms)
    assert res.hits_detected == 5 and res.hits_matched == 5 and res.total >= 95


def test_estimate_bleed_shift():
    bed = np.arange(0.5, 10.0, 1 / 3)  # eighth notes at 90 BPM
    rng = np.random.default_rng(0)
    heard = np.sort(np.concatenate([bed + 0.047 + rng.normal(0, 0.002, len(bed)), [1.1, 4.2]]))
    assert estimate_bleed_shift(heard, bed, 0.12) == pytest.approx(0.047, abs=0.003)
    # Too few matches (a handful of team hits) -> no shift.
    assert estimate_bleed_shift(np.array([0.55, 0.9]), bed, 0.12) == 0.0
    assert estimate_bleed_shift(np.array([]), bed, 0.12) == 0.0


def test_bleed_params_raise_the_noise_gate():
    prof = measure(SON_CLAVE_32, 0.3, 0.02)
    p = bleed_params(
        prof, OnsetParams(noise_floor_db=-70.0), bpm=BPM, bed_start_s=0.5, duration_s=10
    )
    assert p.noise_floor_db == pytest.approx(prof.floor_db)
    quiet = bleed_params(
        prof, OnsetParams(noise_floor_db=-10.0), bpm=BPM, bed_start_s=0.5, duration_s=10
    )
    assert quiet.noise_floor_db == -10.0  # never lowers a louder calibrated floor
