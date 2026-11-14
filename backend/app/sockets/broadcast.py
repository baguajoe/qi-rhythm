"""Server -> Display broadcasts. One Socket.IO room per class session."""

from ..extensions import socketio


def room_for(session_id: int) -> str:
    return f"session:{session_id}"


def broadcast(session_id: int, event: str, payload: dict | None = None) -> None:
    socketio.emit(event, payload or {}, to=room_for(session_id))
