"""Game-mode plug-in interface.

Every game mode implements the same five steps so the round controller, sockets, and UI can
drive any mode generically. Phase 1 ships only Rhythm Recall.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import Any


class GameModeKey(str, enum.Enum):
    RHYTHM_RECALL = "rhythm_recall"
    # TODO(phase-2): FINISH_THE_BEAT, MUSIC_MEMORY, CALL_AND_RESPONSE
    # TODO(phase-5): BEAT_BUILDER, FOLLOW_THE_GROOVE, RHYTHM_AND_MOVEMENT


class GameMode(ABC):
    key: GameModeKey
    label: str

    @abstractmethod
    def setup(self, round_, settings: dict) -> dict:
        """Validate/prepare a round; return mode-specific config stored on the round."""

    @abstractmethod
    def reference(self, round_) -> dict:
        """Describe what the frontend should play/show as the reference (pattern, tempo)."""

    @abstractmethod
    def capture(self, round_) -> dict:
        """Describe the capture window (count-in, record length) for the frontend."""

    @abstractmethod
    def analyze(self, round_, audio: bytes, meta: dict, calibration) -> Any:
        """Run audio analysis on the uploaded take; return an engine result."""

    @abstractmethod
    def score(self, round_, analysis: Any) -> dict:
        """Turn the analysis into Score fields."""


_REGISTRY: dict[GameModeKey, GameMode] = {}


def register(mode: GameMode) -> GameMode:
    _REGISTRY[mode.key] = mode
    return mode


def get_mode(key: str | GameModeKey) -> GameMode:
    try:
        return _REGISTRY[GameModeKey(key)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"unsupported game mode {key!r}") from exc


def available_modes() -> list[GameMode]:
    return list(_REGISTRY.values())
