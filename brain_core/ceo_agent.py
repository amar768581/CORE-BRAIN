"""CEOAgentBrain: ROI-driven executive decision making on the SharedMemoryBus.

The brain reads the SEO strategy and analytics that the other agents have
broadcast onto the bus, then issues a JSON-serializable executive directive:
budget policy, content tone, format choice, an expected ROI index (0-100) and
priorities for the sub-agents. The directive is broadcast back onto the bus as
{"ceo_directive": directive} from sender "CEO_Brain" so every other agent can
act on it.
"""

from __future__ import annotations

import json
from typing import Any, Optional

try:  # Package execution (import brain_core.ceo_agent).
    from brain_core.memory_bus import SharedMemoryBus
    from brain_core.seo_agent import SEOAgent
    from brain_core.llm_client import LLMClient
except ModuleNotFoundError:  # Direct execution: python3 brain_core/ceo_agent.py
    from memory_bus import SharedMemoryBus
    from seo_agent import SEOAgent
    from llm_client import LLMClient


def _str_list(value: Any, limit: int = 6) -> list[str]:
    """Coerce an LLM list-of-strings field into a clean, bounded list."""
    if not isinstance(value, list):
        return []
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:limit]


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

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        """Use an injected LLMClient, or a default one reading the env keys."""
        self.llm = llm if llm is not None else LLMClient()

    def _llm_enrich(
        self, directive: dict, seo_strategy: dict, analytics: dict,
    ) -> Optional[dict]:
        """Ask the LLM for strategic insights and merge them into the directive.

        Deterministic fields (budget policy, tone, format, ROI index, priorities)
        are never overridden. Returns an enriched copy when the model supplies
        usable insights, otherwise None so the caller keeps the rule-based result.
        """
        system_prompt = (
            "You are the CEO Agent Brain of a digital media company. Reply with ONLY "
            "a JSON object (no prose, no markdown fences) with these keys: "
            "content_strategy (array of 3 concise strategic priorities), "
            "key_risks (array of the top risks), "
            "recommended_actions (array of immediate next actions)."
        )
        user_prompt = (
            f"SEO strategy: {json.dumps(seo_strategy, ensure_ascii=False)}\n"
            f"Analytics: {json.dumps(analytics, ensure_ascii=False)}\n"
            f"Current deterministic directive: {json.dumps(directive, ensure_ascii=False)}\n"
            "Produce the strategic insights JSON object described."
        )
        data = self.llm.generate_json(system_prompt, user_prompt)
        if not isinstance(data, dict):
            return None

        insights: dict[str, Any] = {}
        for field in ("content_strategy", "key_risks", "recommended_actions"):
            values = _str_list(data.get(field))
            if values:
                insights[field] = values

        return {**directive, **insights} if insights else None

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

        # Optional LLM enrichment; any failure keeps the rule-based directive.
        enriched = self._llm_enrich(directive, seo_strategy, analytics)
        if enriched is not None:
            directive = enriched
            directive["engine"] = "llm"
        else:
            directive["engine"] = "rule_based"

        bus.broadcast(
            sender="CEO_Brain",
            message=(
                f"Executive directive issued ({directive['engine']} engine): "
                f"{directive['budget_policy']} | "
                f"tone={sentiment} | format={format_choice} | "
                f"expected_roi_index={expected_roi_index}/100."
            ),
            data={"ceo_directive": directive},
        )
        return directive


if __name__ == "__main__":
    # Quick smoke test: pair SharedMemoryBus, SEOAgent and CEOAgentBrain
    # end-to-end across a healthy and a critical budget scenario. Provider
    # keys are popped so the rule-based path stays deterministic.
    import os

    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)

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
    assert healthy["engine"] == "rule_based"
    assert critical["engine"] == "rule_based"
    assert default_directive["engine"] == "rule_based"

    # --- LLM path: a mocked provider enriches without overriding rules ----
    class _FakeLLM:
        def __init__(self, response):
            self.response = response

        def generate_json(self, system_prompt, user_prompt):
            return self.response

    bus5 = SharedMemoryBus()
    bus5.state["trends"] = dict(trends)
    SEOAgent(llm=_FakeLLM(None)).analyze_and_optimize(bus5)  # SEO stays rule-based
    bus5.state["analytics"] = {
        "budget_status": "critical",
        "sentiment": "negative",
        "best_format": "article",
        "roi_score": 30,
    }
    llm_directive = CEOAgentBrain(llm=_FakeLLM({
        "content_strategy": [
            "Double down on organic search",
            "Ship weekly",
            "Repurpose top performers",
        ],
        "key_risks": ["Ad spend freeze", "Thin backlink profile"],
        "recommended_actions": ["Publish 3 SEO articles", "Re-audit top 20 pages"],
    })).make_executive_decision(bus5)

    assert llm_directive["engine"] == "llm"
    assert llm_directive["content_strategy"][0] == "Double down on organic search"
    assert len(llm_directive["key_risks"]) == 2
    # Deterministic fields are never overridden by the model.
    assert llm_directive["budget_policy"] == "Zero Paid Ads — Strict Organic SEO & High Monetization Compliance"
    assert llm_directive["format_choice"] == "ARTICLE"
    assert bus5.state["seo_strategy"]["engine"] == "rule_based"  # mixed engines OK
    assert bus5.state["ceo_directive"] == llm_directive

    # --- Fallback: unusable model output keeps the rule-based directive ----
    fallback_directive = CEOAgentBrain(
        llm=_FakeLLM({"content_strategy": "not-a-list"})
    ).make_executive_decision(bus5)
    assert fallback_directive["engine"] == "rule_based"
    assert "content_strategy" not in fallback_directive

    print("CEOAgentBrain smoke test passed.")
    print(bus.to_json())
