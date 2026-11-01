from __future__ import annotations

import copy
import pickle
import threading
from datetime import datetime, timezone
from typing import Any

_DEFAULT_STATE = {
    "trends": {},
    "seo_strategy": {},
    "analytics": {},
    "ceo_directive": {},
    "messages": [],
}


class SharedMemoryBus:
    """Thread-safe in-memory store with optional on-disk persistence."""

    __slots__ = ("_state", "_lock", "_path")

    def __init__(self, path: str | None = None) -> None:
        self._state = copy.deepcopy(_DEFAULT_STATE)
        self._lock = threading.RLock()
        self._path = path
        if path:
            self._load(self._path)

    def _load(self, path: str) -> None:
        try:
            with open(path, "rb") as fh:
                data = pickle.load(fh)
            if isinstance(data, dict):
                self._state = data
        except (FileNotFoundError, pickle.UnpicklingError, EOFError, AttributeError):
            pass

    def _save(self, path: str) -> None:
        try:
            with open(path, "wb") as fh:
                pickle.dump(self._state, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError:
            pass

    @property
    def state(self) -> dict[str, Any]:
        """Frozen, deep-copied snapshot of the full bus state."""
        with self._lock:
            return copy.deepcopy(self._state)

    def broadcast(self, sender: str, message: str, data: dict[str, Any] | None = None) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            if data:
                for key, value in data.items():
                    if isinstance(value, dict):
                        self._state[key] = {**self._state.get(key, {}), **value}
                    else:
                        self._state[key] = value
            self._state["messages"].append(
                {"timestamp": stamp, "sender": sender, "message": message}
            )
            self._state["messages"] = self._state["messages"][-1000:]
            if self._path:
                self._save(self._path)

    def seed(self, key: str, value: Any, timestamp: str | None = None) -> None:
        stamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            if isinstance(value, dict):
                self._state[key] = {**self._state.get(key, {}), **value}
            else:
                self._state[key] = value
            self._state["messages"].append(
                {"timestamp": stamp, "sender": key, "message": f"seeded {key}"}
            )
            self._state["messages"] = self._state["messages"][-1000:]
            if self._path:
                self._save(self._path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return copy.deepcopy(self._state.get(key, default))

    def update(self, payload: dict[str, Any]) -> None:
        with self._lock:
            for key, value in payload.items():
                if isinstance(value, dict):
                    self._state[key] = {**self._state.get(key, {}), **value}
                else:
                    self._state[key] = value
            if self._path:
                self._save(self._path)

    def export_json(self, path: str | None = None) -> str:
        import json as _json
        snapshot = self.state
        text = _json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return text

    def is_empty(self) -> bool:
        with self._lock:
            return all(not value for value in self._state.values()) and not self._state["messages"]
