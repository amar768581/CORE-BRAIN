"""SharedMemoryBus: inter-agent communication via a shared JSON-serializable state.

Agents broadcast messages to each other; every broadcast is logged with a UTC
timestamp and merged into the bus state, which can be serialized to JSON and
handed to any other agent (or persisted) without loss.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional


class SharedMemoryBus:
    """A JSON-serializable shared state bus for inter-agent communication."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "trends": {},
            "seo_strategy": {},
            "analytics": {},
            "ceo_directive": {},
            "messages": [],
        }

    @staticmethod
    def _utc_now() -> str:
        """Return the current UTC time as an ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def broadcast(self, sender: str, message: str, data: Optional[dict] = None) -> dict:
        """Log an inter-agent message with a UTC timestamp and update state.

        Args:
            sender: Name/id of the agent sending the message.
            message: Human-readable message text.
            data: Optional JSON-serializable payload. When provided, it is
                merged into the top-level state (e.g. {"trends": {...}}).

        Returns:
            The full updated state dictionary.
        """
        record = {
            "sender": sender,
            "message": message,
            "timestamp": self._utc_now(),
            "data": data,
        }
        self.state["messages"].append(record)

        if data:
            for key, value in data.items():
                if key in self.state and isinstance(self.state[key], dict) and isinstance(value, dict):
                    self.state[key].update(value)
                else:
                    self.state[key] = value

        return self.state

    def to_json(self) -> str:
        """Serialize the entire bus state to a JSON string."""
        return json.dumps(self.state, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, payload: str) -> "SharedMemoryBus":
        """Rebuild a bus from a previously serialized JSON state."""
        bus = cls()
        bus.state = json.loads(payload)
        return bus


if __name__ == "__main__":
    # Quick smoke test when executed directly.
    bus = SharedMemoryBus()

    bus.broadcast(
        "ceo",
        "Push a Q4 SEO sprint focused on long-tail keywords.",
        data={"ceo_directive": {"priority": "seo", "quarter": "Q4"}},
    )
    bus.broadcast(
        "seo_agent",
        "Long-tail clusters mapped; starting content briefs.",
        data={"seo_strategy": {"focus": "long-tail", "status": "in_progress"}},
    )
    bus.broadcast(
        "analytics_agent",
        "Organic traffic up 12% week over week.",
        data={"analytics": {"organic_wow": 0.12}},
    )

    # State must survive a JSON round-trip.
    restored = SharedMemoryBus.from_json(bus.to_json())
    assert restored.state == bus.state, "JSON round-trip lost state"
    assert len(restored.state["messages"]) == 3
    assert all("timestamp" in m for m in restored.state["messages"])
    assert restored.state["ceo_directive"]["priority"] == "seo"

    print("SharedMemoryBus smoke test passed.")
    print(bus.to_json())
