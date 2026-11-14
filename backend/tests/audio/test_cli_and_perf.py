import io
import json
import time

from app.audio.cli import main
from app.audio.scoring import analyze_take
from app.audio.synth import SynthOptions, render

from .conftest import EIGHT_HIT


def test_cli_synth_then_score(tmp_path, capsys):
    pat = tmp_path / "pattern.json"
    pat.write_text(json.dumps({"title": "x", "pattern": EIGHT_HIT}))
    wav = tmp_path / "take.wav"
    assert (
        main(
            [
                "synth",
                "--pattern",
                str(pat),
                "--bpm",
                "90",
                "--out",
                str(wav),
                "--jitter-ms",
                "5",
                "--clicks",
            ]
        )
        == 0
    )
    assert wav.exists()
    assert main(["score", "--pattern", str(pat), "--bpm", "90", "--wav", str(wav)]) == 0
    out = capsys.readouterr().out
    assert "Total" in out and "Pattern accuracy" in out
    total = float(next(line for line in out.splitlines() if "Total" in line).split()[-1])
    assert total >= 95


def test_cli_json_output(tmp_path, capsys):
    pat = tmp_path / "p.json"
    pat.write_text(json.dumps(EIGHT_HIT))
    wav = tmp_path / "t.wav"
    render(EIGHT_HIT, SynthOptions(noise_level=0.2)).write(wav)
    capsys.readouterr()
    main(["score", "--pattern", str(pat), "--bpm", "90", "--wav", str(wav), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["needs_review"] is True


def test_analysis_of_15_second_clip_is_under_2_seconds():
    long_pattern = {
        "count_in_beats": 4,
        "length_beats": 16,
        "events": [{"beat": b * 0.5, "voice": "high"} for b in range(32)],
    }
    s = render(long_pattern, SynthOptions(bpm=96, sr=48000, tail_beats=4, noise_level=0.005))
    assert 14.0 <= len(s.audio) / s.sr <= 16.5
    buf = io.BytesIO()
    import soundfile as sf

    sf.write(buf, s.audio, s.sr, format="WAV", subtype="PCM_16")
    data = buf.getvalue()
    t0 = time.perf_counter()
    res = analyze_take(data, long_pattern, bpm=96, countin_start_s=s.countin_start_s)
    elapsed = time.perf_counter() - t0
    assert res.total >= 95
    assert elapsed < 2.0, f"analysis took {elapsed:.2f}s"
