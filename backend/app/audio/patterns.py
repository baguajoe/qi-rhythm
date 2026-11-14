"""Helpers for the beat-relative rhythm pattern format.

Pattern JSON::

    {
      "subdivision": 4,
      "events": [{"beat": 0.0, "voice": "low", "accent": true}, ...],
      "count_in_beats": 4
    }

``beat`` is measured in quarter-note beats from the start of the pattern (after the count-in).
``voice`` is one of low / high / shaker / clap. Phase 1 scoring ignores voice (timing only).
"""

from __future__ import annotations

from dataclasses import dataclass

VOICES = ("low", "high", "shaker", "clap")


@dataclass(frozen=True)
class PatternEvent:
    index: int
    beat: float
    voice: str
    accent: bool = False


def parse_events(pattern: dict) -> list[PatternEvent]:
    """Return pattern events sorted by beat, validating the basic shape."""
    raw = pattern.get("events")
    if not isinstance(raw, list) or not raw:
        raise ValueError("pattern must contain a non-empty 'events' list")
    events = []
    for ev in sorted(raw, key=lambda e: float(e["beat"])):
        voice = ev.get("voice", "low")
        if voice not in VOICES:
            raise ValueError(f"unknown voice {voice!r}; expected one of {VOICES}")
        beat = float(ev["beat"])
        if beat < 0:
            raise ValueError("event beats must be >= 0")
        events.append(PatternEvent(len(events), beat, voice, bool(ev.get("accent", False))))
    return events


def count_in_beats(pattern: dict, default: int = 4) -> int:
    return int(pattern.get("count_in_beats", default))


def length_beats(pattern: dict) -> float:
    """Pattern length in beats; explicit ``length_beats`` or rounded up to the next full bar."""
    if "length_beats" in pattern:
        return float(pattern["length_beats"])
    last = max(e.beat for e in parse_events(pattern))
    return float(int(last // 4 + 1) * 4)


def seconds_per_beat(bpm: float) -> float:
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    return 60.0 / bpm
