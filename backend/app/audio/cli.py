"""Command-line tools for the analysis engine.

Examples::

    python -m app.audio.cli score --pattern clave.json --bpm 90 --wav take.wav
    python -m app.audio.cli synth --pattern clave.json --bpm 90 --out take.wav --jitter-ms 15
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .onset import OnsetParams
from .scoring import PRESETS, analyze_take
from .synth import SynthOptions, render


def _load_pattern(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    return data.get("pattern", data)  # accept a full Rhythm record or a bare pattern


def cmd_score(args) -> int:
    pattern = _load_pattern(args.pattern)
    params = OnsetParams(threshold=args.threshold, noise_floor_db=args.noise_floor_db)
    t0 = time.perf_counter()
    res = analyze_take(
        args.wav,
        pattern,
        bpm=args.bpm,
        countin_start_s=args.countin_start,
        latency_ms=args.latency_ms,
        preset=args.preset,
        onset_params=params,
    )
    elapsed = time.perf_counter() - t0
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0
    al = res.alignment
    print(f"Preset: {PRESETS[res.preset].label}   Mode: {res.mode}   ({elapsed:.2f}s)")
    print(f"  Pattern accuracy   {res.pattern_accuracy:6.1f}")
    print(f"  Timing accuracy    {res.timing_accuracy:6.1f}")
    print(f"  Tempo consistency  {res.tempo_consistency:6.1f}")
    print(f"  Completion         {res.completion:6.1f}")
    print(f"  Total              {res.total:6.1f}")
    print(
        f"Hits: expected {res.hits_expected}, heard {res.hits_detected}, "
        f"matched {res.hits_matched}, missed {len(al['missed'])}, extra {len(al['extras'])}"
    )
    print(f"Global offset {al['global_offset_ms']:+.0f} ms   Confidence {res.confidence:.2f}")
    if res.needs_review:
        print("NEEDS REVIEW: " + " ".join(res.review_reasons))
    return 0


def cmd_synth(args) -> int:
    pattern = _load_pattern(args.pattern)
    opts = SynthOptions(
        bpm=args.bpm,
        jitter_ms=args.jitter_ms,
        global_offset_ms=args.offset_ms,
        miss_count=args.miss,
        extra_count=args.extra,
        noise_level=args.noise,
        rumble_level=args.rumble,
        tempo_scale=args.tempo_scale,
        count_in_clicks=args.clicks,
        seed=args.seed,
    )
    res = render(pattern, opts)
    res.write(args.out)
    print(f"Wrote {args.out}  (count-in starts at {res.countin_start_s:.3f}s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.audio.cli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="Score a recorded take against a pattern")
    s.add_argument("--pattern", required=True, help="pattern JSON file")
    s.add_argument("--bpm", type=float, required=True)
    s.add_argument("--wav", required=True)
    s.add_argument(
        "--countin-start", type=float, default=0.5, help="seconds from clip start to count-in"
    )
    s.add_argument("--latency-ms", type=float, default=0.0)
    s.add_argument("--preset", choices=sorted(PRESETS), default="gentle")
    s.add_argument("--threshold", type=float, default=0.07)
    s.add_argument("--noise-floor-db", type=float, default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_score)

    g = sub.add_parser("synth", help="Render a synthetic take for testing")
    g.add_argument("--pattern", required=True)
    g.add_argument("--bpm", type=float, required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--jitter-ms", type=float, default=0.0)
    g.add_argument("--offset-ms", type=float, default=0.0)
    g.add_argument("--miss", type=int, default=0)
    g.add_argument("--extra", type=int, default=0)
    g.add_argument("--noise", type=float, default=0.0)
    g.add_argument("--rumble", type=float, default=0.0)
    g.add_argument("--tempo-scale", type=float, default=1.0)
    g.add_argument("--clicks", action="store_true", help="include count-in click bleed")
    g.add_argument("--seed", type=int, default=0)
    g.set_defaults(func=cmd_synth)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
