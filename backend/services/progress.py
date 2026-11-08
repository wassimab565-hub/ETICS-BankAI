import threading

_lock = threading.Lock()
_state: dict[int, dict] = {}


def update(document_id: int, stage: str, done: int, total: int) -> None:
    """Progress of the analysis of a document. Kept in memory only (lost on restart)."""
    with _lock:
        _state[document_id] = {"stage": stage, "done": done, "total": total}


def get(document_id: int) -> dict | None:
    with _lock:
        state = _state.get(document_id)
        return dict(state) if state else None


def clear(document_id: int) -> None:
    with _lock:
        _state.pop(document_id, None)