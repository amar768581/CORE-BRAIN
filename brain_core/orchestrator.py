"""CoreBrainOrchestrator: single entry point for the Core Brain pipeline.

Wires together SharedMemoryBus, SEOAgent and CEOAgentBrain so one full cycle -
seed context, run SEO analysis, issue the executive directive - happens in a
single call, with every step logged as an inter-agent message on the shared bus.
"""

from __future__ import annotations

import os
from typing import Any

try:  # Package execution (import brain_core.orchestrator).
    from brain_core.memory_bus import SharedMemoryBus
    from brain_core.seo_agent import SEOAgent
    from brain_core.ceo_agent import CEOAgentBrain
except ModuleNotFoundError:  # Direct execution: python3 brain_core/orchestrator.py
    from memory_bus import SharedMemoryBus
    from seo_agent import SEOAgent
    from ceo_agent import CEOAgentBrain


class CoreBrainOrchestrator:
    """Coordinates SharedMemoryBus, SEOAgent and CEOAgentBrain over one cycle."""

    def __init__(self) -> None:
        self.bus = SharedMemoryBus()
        self.seo_agent = SEOAgent()
        self.ceo_agent = CEOAgentBrain()

    @staticmethod
    def _normalize_trends(trends: Any) -> dict:
        """Convert seeded trends into the bus's ordered dict form.

        The bus stores trends as a dict whose insertion order encodes rank
        (first entry = top trend, which SEOAgent reads). Lists of names, lists
        of metadata dicts (topic/name/title/trend keys) and already-ordered
        dicts are all accepted; anything falsy yields an empty dict.
        """
        if not trends:
            return {}
        if isinstance(trends, dict):
            return dict(trends)
        if isinstance(trends, (list, tuple)):
            normalized: dict[str, Any] = {}
            for entry in trends:
                if isinstance(entry, dict):
                    key = next(
                        (
                            str(entry[field])
                            for field in ("topic", "name", "title", "trend")
                            if entry.get(field)
                        ),
                        str(entry),
                    )
                    normalized.setdefault(key, entry)
                elif str(entry).strip():
                    normalized.setdefault(str(entry).strip(), {})
            return normalized
        return {str(trends): {}}

    def run_cycle(
        self,
        topic: str = None,
        trends: list = None,
        analytics: dict = None,
    ) -> dict:
        """Run one full Core Brain cycle and return the bus state snapshot.

        Seeds trends and analytics onto the bus (logging a "System_Init"
        broadcast when anything is provided), runs the SEO agent, then the CEO
        brain, and returns the resulting state.

        Args:
            topic: Optional explicit topic for the SEO agent; otherwise the
                top seeded trend, then the built-in default, is used.
            trends: Optional trends to seed - a list of names and/or metadata
                dicts, or a pre-built ordered dict (first entry = top trend).
            analytics: Optional analytics for the CEO brain (budget_status,
                sentiment, best_format, roi_score); its defaults apply to any
                key left out.

        Returns:
            A snapshot of the full bus state: seeded trends/analytics,
            "seo_strategy", "ceo_directive" and every inter-agent "message".
        """
        seed_data: dict[str, Any] = {}
        seed_notes: list[str] = []

        seeded_trends = self._normalize_trends(trends)
        if seeded_trends:
            seed_data["trends"] = seeded_trends
            seed_notes.append(
                f"{len(seeded_trends)} trend(s), top='{next(iter(seeded_trends))}'"
            )

        if analytics:
            seed_data["analytics"] = dict(analytics)
            seed_notes.append(
                "analytics: "
                + ", ".join(f"{key}={value}" for key, value in analytics.items())
            )

        if seed_data:
            self.bus.broadcast(
                sender="System_Init",
                message="Core Brain cycle initialized with " + "; ".join(seed_notes) + ".",
                data=seed_data,
            )

        self.seo_agent.analyze_and_optimize(self.bus, topic=topic)
        self.ceo_agent.make_executive_decision(self.bus)

        return dict(self.bus.state)  # snapshot; nested agent payloads are shared


if __name__ == "__main__":
    # Quick smoke test when executed directly. Provider keys are popped so the
    # rule-based path stays deterministic regardless of the host environment.
    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)

    orch = CoreBrainOrchestrator()
    snapshot = orch.run_cycle(
        trends=[
            {"topic": "Autonomous AI & Digital Media Growth", "volume": "905K"},
            "AI Video Editing Tools",
        ],
        analytics={
            "budget_status": "healthy",
            "sentiment": "positive",
            "best_format": "video",
            "roi_score": 82,
        },
    )

    # The snapshot contains everything the agents produced, but is not the live state.
    assert snapshot == orch.bus.state
    assert snapshot is not orch.bus.state, "run_cycle must return a snapshot"
    assert snapshot["seo_strategy"]["topic"] == "Autonomous AI & Digital Media Growth"
    assert snapshot["ceo_directive"]["budget_policy"].startswith("Balanced Growth")
    senders = [m["sender"] for m in snapshot["messages"]]
    assert senders == ["System_Init", "SEO_Agent", "CEO_Brain"], senders
    assert snapshot["seo_strategy"]["engine"] == "rule_based"
    assert snapshot["ceo_directive"]["engine"] == "rule_based"

    # An explicit topic overrides the seeded trend; analytics defaults fill in.
    orch2 = CoreBrainOrchestrator()
    snap2 = orch2.run_cycle(topic="Best Vegan Protein Powders", trends=["Ignored Trend"])
    assert snap2["seo_strategy"]["topic"] == "Best Vegan Protein Powders"
    assert snap2["ceo_directive"]["sentiment"] == "positive"
    assert [m["sender"] for m in snap2["messages"]][0] == "System_Init"

    # A critical budget seeds through to the directive.
    orch3 = CoreBrainOrchestrator()
    snap3 = orch3.run_cycle(
        trends=["AI Video Editing Tools"],
        analytics={
            "budget_status": "critical",
            "sentiment": "negative",
            "best_format": "article",
            "roi_score": 30,
        },
    )
    assert snap3["ceo_directive"]["budget_policy"].startswith("Zero Paid Ads")
    assert snap3["ceo_directive"]["format_choice"] == "ARTICLE"
    assert (
        snap3["ceo_directive"]["expected_roi_index"]
        < snapshot["ceo_directive"]["expected_roi_index"]
    )

    # No arguments at all: the default topic flows through with no init broadcast.
    snap4 = CoreBrainOrchestrator().run_cycle()
    assert snap4["seo_strategy"]["topic"]
    assert snap4["ceo_directive"]["budget_status"] == "healthy"
    assert [m["sender"] for m in snap4["messages"]] == ["SEO_Agent", "CEO_Brain"]

    print("CoreBrainOrchestrator smoke test passed.")
    print(orch.bus.to_json())
