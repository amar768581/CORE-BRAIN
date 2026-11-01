"""CEOAgentBrain: ROI-driven executive decision making on the SharedMemoryBus.

The brain reads the SEO strategy and analytics that the other agents have
broadcast onto the bus, then issues a JSON-serializable executive directive:
budget policy, content tone, format choice, an expected ROI index (0-100) and
priorities for the sub-agents. The directive is broadcast back onto the bus as
{"ceo_directive": directive} from sender "CEO_Brain" so every other agent can
act on it.
"""

from __future__ import annotations

from typing import Any

try:  # Package execution (import brain_core.ceo_agent).
    from brain_core.memory_bus import SharedMemoryBus
    from brain_core.seo_agent import SEOAgent
except ModuleNotFoundError:  # Direct execution: python3 brain_core/ceo_agent.py
    from memory_bus import SharedMemoryBus
    from seo_agent import SEOAgent


class CEOAgentBrain:
    """Issues executive directives from the shared bus state."""

    BUDGET_POLICIES = {
        "critical": "Zero Paid Ads — Strict Organic SEO & High Monetization Compliance",
        "warning": "Conservative Spend — Retargeting & Organic Growth Focus",
        "healthy": "Balanced Growth — Organic + Boosted Viral Distribution",
    }

    CONTENT_TONES = {
        "positive": "Aspirational & Bold — Ride the Momentum",
        "negative": "Empathetic & Reassuring — Address Concerns Directly",
        "neutral": "Informative & Educational — Build Trust with Value",
    }

    FORMAT_MAP = {
        "video": "VIDEO",
        "short": "VIDEO",
        "shorts": "VIDEO",
        "reel": "VIDEO",
        "article": "ARTICLE",
        "blog": "ARTICLE",
        "text": "ARTICLE",
        "hybrid": "HYBRID",
    }

    # Budget risk adjustments applied to the blended ROI index.
    BUDGET_RISK_ADJUSTMENT = {"critical": -8, "warning": -4, "healthy": 0}

    @staticmethod
    def _score(value: Any, default: int) -> int:
        """Coerce a bus-provided score to an int in [0, 100]."""
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return default

    def _budget_status(self, analytics: dict) -> str:
        status = str(analytics.get("budget_status", "healthy")).strip().lower()
        return status if status in self.BUDGET_POLICIES else "healthy"

    def _sentiment(self, analytics: dict) -> str:
        sentiment = str(analytics.get("sentiment", "positive")).strip().lower()
        return sentiment if sentiment in self.CONTENT_TONES else "neutral"

    def _format_choice(self, analytics: dict) -> str:
        best = str(analytics.get("best_format", "video")).strip().lower()
        return self.FORMAT_MAP.get(best, "HYBRID")

    def _expected_roi_index(self, seo_score: int, roi_score: int, budget_status: str) -> int:
        """Blend SEO and ROI scores into a risk-adjusted 0-100 index."""
        blended = 0.6 * seo_score + 0.4 * roi_score
        adjusted = blended + self.BUDGET_RISK_ADJUSTMENT[budget_status]
        return max(0, min(100, round(adjusted)))

    def _sub_agent_priorities(
        self, budget_status: str, seo_score: int, expected_roi_index: int,
        sentiment: str, format_choice: str,
    ) -> dict[str, str]:
        """Derive per-sub-agent priorities from the current bus picture."""
        if budget_status == "critical" or seo_score < 60:
            seo_priority = "CRITICAL"
        elif seo_score < 80:
            seo_priority = "HIGH"
        else:
            seo_priority = "MEDIUM"

        if expected_roi_index >= 75:
            content_priority = "CRITICAL"
        elif expected_roi_index >= 50:
            content_priority = "HIGH"
        else:
            content_priority = "MEDIUM"

        compliance_priority = {
            "critical": "CRITICAL",
            "warning": "HIGH",
            "healthy": "MEDIUM",
        }[budget_status]

        if sentiment == "positive" and format_choice in ("VIDEO", "HYBRID"):
            distribution_priority = "CRITICAL"
        elif sentiment == "positive":
            distribution_priority = "HIGH"
        else:
            distribution_priority = "MEDIUM"

        return {
            "seo_optimization": seo_priority,
            "content_creation": content_priority,
            "compliance_check": compliance_priority,
            "social_distribution": distribution_priority,
        }

    def make_executive_decision(self, bus: SharedMemoryBus) -> dict:
        """Issue an executive directive from the bus state and broadcast it.

        Reads "seo_strategy" and "analytics" from bus.state (falling back to
        budget_status="healthy", sentiment="positive", best_format="video" and
        roi_score=78 when absent), derives the budget policy, content tone,
        format choice, expected ROI index and sub-agent priorities, broadcasts
        the directive from sender "CEO_Brain" and returns it.

        Args:
            bus: The shared memory bus holding agent state.

        Returns:
            The ceo_directive dictionary (also stored on
            bus.state["ceo_directive"] by the broadcast).
        """
        seo_strategy: dict = bus.state.get("seo_strategy") or {}
        analytics: dict = bus.state.get("analytics") or {}

        seo_score = self._score(seo_strategy.get("seo_score"), 0)
        roi_score = self._score(analytics.get("roi_score"), 78)
        budget_status = self._budget_status(analytics)
        sentiment = self._sentiment(analytics)
        format_choice = self._format_choice(analytics)

        expected_roi_index = self._expected_roi_index(seo_score, roi_score, budget_status)
        priorities = self._sub_agent_priorities(
            budget_status, seo_score, expected_roi_index, sentiment, format_choice,
        )

        directive: dict[str, Any] = {
            "budget_status": budget_status,
            "budget_policy": self.BUDGET_POLICIES[budget_status],
            "sentiment": sentiment,
            "content_tone": self.CONTENT_TONES[sentiment],
            "format_choice": format_choice,
            "seo_score": seo_score,
            "roi_score": roi_score,
            "expected_roi_index": expected_roi_index,
            "sub_agent_priorities": priorities,
        }

        bus.broadcast(
            sender="CEO_Brain",
            message=(
                f"Executive directive issued: {directive['budget_policy']} | "
                f"tone={sentiment} | format={format_choice} | "
                f"expected_roi_index={expected_roi_index}/100."
            ),
            data={"ceo_directive": directive},
        )
        return directive


if __name__ == "__main__":
    # Quick smoke test: pair SharedMemoryBus, SEOAgent and CEOAgentBrain
    # end-to-end across a healthy and a critical budget scenario.
    trends = {"Autonomous AI & Digital Media Growth": {"volume": "905K", "growth": "+38%"}}
    brain = CEOAgentBrain()

    # --- Scenario 1: healthy budget -------------------------------------
    bus = SharedMemoryBus()
    bus.state["trends"] = dict(trends)
    seo_payload = SEOAgent().analyze_and_optimize(bus)
    bus.state["analytics"] = {
        "budget_status": "healthy",
        "sentiment": "positive",
        "best_format": "video",
        "roi_score": 82,
    }
    healthy = brain.make_executive_decision(bus)

    assert bus.state["ceo_directive"] == healthy, "ceo_directive not recorded on the bus"
    assert healthy["budget_policy"] == "Balanced Growth — Organic + Boosted Viral Distribution"
    assert healthy["format_choice"] == "VIDEO"
    assert 0 <= healthy["expected_roi_index"] <= 100
    assert healthy["expected_roi_index"] > 0.5 * seo_payload["seo_score"]  # ROI blend rewards strong SEO
    assert healthy["sub_agent_priorities"]["social_distribution"] == "CRITICAL"
    assert healthy["sub_agent_priorities"]["compliance_check"] == "MEDIUM"
    healthy_senders = [m["sender"] for m in bus.state["messages"]]
    assert "SEO_Agent" in healthy_senders, "SEO_Agent message not logged"
    assert "CEO_Brain" in healthy_senders, "CEO_Brain message not logged"

    # --- Scenario 2: critical budget ------------------------------------
    bus2 = SharedMemoryBus()
    bus2.state["trends"] = dict(trends)
    SEOAgent().analyze_and_optimize(bus2)
    bus2.state["analytics"] = {
        "budget_status": "critical",
        "sentiment": "negative",
        "best_format": "article",
        "roi_score": 30,
    }
    critical = brain.make_executive_decision(bus2)

    assert bus2.state["ceo_directive"] == critical, "ceo_directive not recorded on the bus"
    assert critical["budget_policy"] == "Zero Paid Ads — Strict Organic SEO & High Monetization Compliance"
    assert critical["content_tone"] != healthy["content_tone"], "tone must adapt to sentiment"
    assert critical["format_choice"] == "ARTICLE"
    assert critical["expected_roi_index"] < healthy["expected_roi_index"], "critical budget must lower expected ROI"
    assert critical["sub_agent_priorities"]["compliance_check"] == "CRITICAL"
    assert critical["sub_agent_priorities"]["seo_optimization"] == "CRITICAL"
    assert critical["sub_agent_priorities"]["social_distribution"] == "MEDIUM"
    critical_senders = [m["sender"] for m in bus2.state["messages"]]
    assert "SEO_Agent" in critical_senders and "CEO_Brain" in critical_senders

    # --- Defaults: empty bus (no trends, no seo_strategy, no analytics) --
    default_directive = brain.make_executive_decision(SharedMemoryBus())
    assert default_directive["budget_status"] == "healthy"
    assert default_directive["sentiment"] == "positive"
    assert default_directive["format_choice"] == "VIDEO"
    assert default_directive["roi_score"] == 78
    assert default_directive["seo_score"] == 0
    assert default_directive["expected_roi_index"] == 31  # round(0.6*0 + 0.4*78), healthy adjustment

    print("CEOAgentBrain smoke test passed.")
    print(bus.to_json())
