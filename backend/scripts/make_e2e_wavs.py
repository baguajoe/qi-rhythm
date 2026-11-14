"""Generate the WAV files the Playwright suite feeds into Chromium's fake microphone.

Chromium (--use-file-for-fake-audio-capture) restarts the file from 0 each time the page opens
the microphone, so hits are placed relative to the moment the app opens the mic:

- turn takes: the app opens the mic, marks the round 'recording', then starts the count-in about
  ``--turn-lead`` seconds later; hits follow at the seeded rhythm's beat times.
- calibration: hits line up with the 8 tap-test clicks (80 bpm) ``--cal-lead`` seconds in.
- backing music: two loops to upload on the Backing music page (full + groove only), the groove
  alone as the room mic hears it during "Measure music level" (``--music-lead`` s in), and a
  team take with the groove playing under it (groove starts with the count-in).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audio.synth import (  # noqa: E402
    DEFAULT_BED,
    SynthOptions,
    _mix,
    _render_bed,
    render,
    voice_sample,
    write_wav,
)
from app.seed.library import GENRES  # noqa: E402

RHYTHM_SLUG = "latin-son-clave-32"
SR = 48000


def find_rhythm(slug: str) -> dict:
    for g in GENRES:
        for r in g["rhythms"]:
            if r["slug"] == slug:
                return r
    raise SystemExit(f"rhythm {slug} not found")


BED_LEVEL, PAD_LEVEL = 0.3, 0.02  # groove as heard by the room mic (quieter than the team)


def loop_file(path: Path, bpm: float, bars: int, pattern: dict | None = None) -> None:
    """A stereo 24-bit 48 kHz loop exactly ``bars`` x 4 beats long, like a Cubase export."""
    spb = 60.0 / bpm
    buf = np.zeros(int(round(bars * 4 * spb * SR)))
    rng = np.random.default_rng(5)
    _render_bed(buf, 0.0, spb, SynthOptions(sr=SR, bpm=bpm, bed=DEFAULT_BED, bed_level=0.5), rng)
    for ev in (pattern or {}).get("events", []):
        _mix(buf, voice_sample(ev["voice"], SR, rng), ev["beat"] * spb, SR, 0.6)
    import soundfile as sf

    sf.write(str(path), np.stack([np.clip(buf, -1, 1)] * 2, axis=1), SR, subtype="PCM_24")


def write_music(out: Path, pattern: dict, bpm: float, args) -> None:
    loop_file(out / "groove-full.wav", bpm, 2, pattern)
    loop_file(out / "groove-bed.wav", bpm, 1)
    room = dict(bpm=bpm, sr=SR, noise_level=0.002, bed=DEFAULT_BED, bed_level=BED_LEVEL)
    render(
        pattern,
        SynthOptions(
            lead_in_s=args.music_lead,
            team_silent=True,
            bed_pad_level=PAD_LEVEL,
            tail_beats=8,
            seed=6,
            **room,
        ),
    ).write(out / "music-measure.wav")
    render(
        pattern,
        SynthOptions(
            lead_in_s=args.turn_lead,
            jitter_ms=4,
            bed_pad_level=PAD_LEVEL,
            tail_beats=6,
            seed=7,
            **room,
        ),
    ).write(out / "music-turn.wav")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turn-lead", type=float, default=0.30)
    ap.add_argument("--cal-lead", type=float, default=0.27)
    ap.add_argument("--music-lead", type=float, default=0.20)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rhythm = find_rhythm(RHYTHM_SLUG)
    pattern, bpm = rhythm["pattern"], rhythm["bpm"]
    common = dict(bpm=bpm, sr=SR, lead_in_s=args.turn_lead, noise_level=0.002, tail_beats=6)

    render(pattern, SynthOptions(jitter_ms=4, seed=1, **common)).write(out / "perfect.wav")
    render(pattern, SynthOptions(jitter_ms=4, seed=2, miss_indices=[1, 3], **common)).write(
        out / "missed.wav"
    )
    rng = np.random.default_rng(3)
    write_wav(out / "silence.wav", (rng.standard_normal(SR * 14) * 0.0005).astype(np.float32), SR)

    taps = {
        "count_in_beats": 0,
        "length_beats": 8,
        "events": [{"beat": b, "voice": "shaker"} for b in range(8)],
    }
    render(
        taps,
        SynthOptions(
            bpm=80, sr=SR, lead_in_s=args.cal_lead, noise_level=0.002, tail_beats=4, seed=4
        ),
    ).write(out / "calibration.wav")

    write_music(out, pattern, bpm, args)

    meta = {
        "rhythm_slug": RHYTHM_SLUG,
        "title": rhythm["title"],
        "bpm": bpm,
        "hits": len(pattern["events"]),
        "missed": 2,
        "turn_lead": args.turn_lead,
        "cal_lead": args.cal_lead,
        "music_lead": args.music_lead,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote e2e WAVs to {out}")


if __name__ == "__main__":
    main()
