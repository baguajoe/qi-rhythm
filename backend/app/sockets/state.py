"""Live (in-memory) display state per class session plus DB-backed snapshots.

The live part (phase, countdown, focus) is ephemeral UI state, so it is kept in process memory.
Production runs a single gevent worker; to scale out, add a Redis message queue and move this
into Redis. TODO(phase-5): Redis-backed live state for multi-worker / multi-site tournaments.
"""

from __future__ import annotations

import threading

from ..models import ClassSession

_LOCK = threading.Lock()
_LIVE: dict[int, dict] = {}


def live(session_id: int) -> dict:
    with _LOCK:
        return dict(_LIVE.get(session_id, {"phase": "idle"}))


def update_live(session_id: int, **changes) -> dict:
    with _LOCK:
        cur = _LIVE.setdefault(session_id, {"phase": "idle"})
        cur.update(changes)
        return dict(cur)


def clear_live(session_id: int) -> None:
    with _LOCK:
        _LIVE.pop(session_id, None)


def snapshot(sess: ClassSession) -> dict:
    """Everything a Display needs to render correctly after (re)connecting."""
    from ..services.game import round_payload, scoreboard, session_settings

    last = sess.rounds[-1] if sess.rounds else None
    current = live(sess.id)
    if last is not None and current.get("phase") in (None, "idle"):
        # Derive phase from the DB if no live phase was recorded (e.g. after a server restart).
        current["phase"] = {
            "scored": "scored",
            "overridden": "scored",
            "analyzing": "analyzing",
        }.get(last.status, "idle")
    if sess.ended_at:
        current["phase"] = "ended"
    return {
        "session_id": sess.id,
        "settings": session_settings(sess),
        "ended": sess.ended_at is not None,
        "live": current,
        "round": round_payload(last) if last else None,
        "scoreboard": scoreboard(sess),
    }
