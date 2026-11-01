"""SEOAgent: keyword research and viral content optimization on the SharedMemoryBus.

The agent derives its topic from the top trend on the bus (or an explicitly
passed topic), then produces a JSON-serializable SEO payload — primary
keywords, long-tail keywords, search intent, a viral hook, hashtags and a
0-100 seo_score — and broadcasts it back onto the bus for the other agents.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

try:  # Package execution (import brain_core.seo_agent).
    from brain_core.memory_bus import SharedMemoryBus
except ModuleNotFoundError:  # Direct execution: python3 brain_core/seo_agent.py
    from memory_bus import SharedMemoryBus

DEFAULT_TOPIC = "Autonomous AI & Digital Media Growth"

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "its", "of", "on", "or", "the", "to", "too", "with", "your",
}

_INTENT_SIGNALS = {
    "commercial": {
        "best", "buy", "cheap", "compare", "deal", "deals", "price",
        "pricing", "review", "reviews", "service", "services", "tool",
        "tools", "vs",
    },
    "viral_discovery": {
        "discovery", "explode", "exploding", "growth", "hype", "media",
        "news", "reel", "reels", "share", "shorts", "social", "trend",
        "trending", "viral", "watch",
    },
}


class SEOAgent:
    """Produces SEO/viral-optimization payloads from trends on the shared bus."""

    def _resolve_topic(self, bus: SharedMemoryBus) -> str:
        """Pick up the top trend on the bus, falling back to the default topic."""
        trends: Any = bus.state.get("trends") or {}
        if isinstance(trends, dict) and trends:
            # Dicts preserve insertion order: the first entry is the top trend.
            key, value = next(iter(trends.items()))
            if isinstance(value, dict):
                for field in ("topic", "name", "title", "trend"):
                    if value.get(field):
                        return str(value[field])
            if isinstance(value, str) and value.strip():
                return value.strip()
            return str(key)
        return DEFAULT_TOPIC

    @staticmethod
    def _tokens(topic: str) -> list[str]:
        """Lowercase, punctuation-free, stopword-free keywords from the topic."""
        words = re.findall(r"[a-z0-9]+", topic.lower())
        return [w for w in words if w not in _STOPWORDS]

    @classmethod
    def _primary_keywords(cls, topic: str) -> list[str]:
        """Clean primary keywords: the topic's significant words, deduped."""
        seen: dict[str, None] = {}
        for word in cls._tokens(topic):
            seen.setdefault(word)
        return list(seen)

    @classmethod
    def _secondary_keywords(cls, topic: str, primary: list[str]) -> list[str]:
        """Secondary long-tail keywords built around the primary terms."""
        core = " ".join(primary[:4]) if primary else topic.lower().strip()
        if not core:
            return []
        year = datetime.now(timezone.utc).year
        return [
            f"best {core} tools",
            f"how {core} works",
            f"top {core} trends {year}",
            f"{core} examples and results",
        ]

    @classmethod
    def _search_intent(cls, topic: str, primary: list[str]) -> str:
        """Classify search intent from keyword signals."""
        tokens = set(primary or cls._tokens(topic))
        if tokens & _INTENT_SIGNALS["viral_discovery"]:
            return "viral_discovery"
        if tokens & _INTENT_SIGNALS["commercial"]:
            return "commercial"
        return "informational"

    @staticmethod
    def _viral_hook(topic: str, intent: str) -> str:
        """High-CTR viral hook/headline matched to the search intent."""
        year = datetime.now(timezone.utc).year
        if intent == "commercial":
            return f"Top 7 {topic} Picks for {year} — Tested So You Don't Have To"
        if intent == "informational":
            return f"{topic} Explained: The Definitive Guide for {year}"
        return f"{topic} Is Exploding — The Trend Everyone's Watching in {year}"

    @classmethod
    def _hashtags(cls, primary: list[str]) -> list[str]:
        """Recommended hashtags: primary keywords plus evergreen SEO tags."""
        tags = [
            "#" + (word.upper() if len(word) <= 2 else word.title())
            for word in primary[:4]
        ]
        for evergreen in ("#SEO", "#ContentStrategy", "#Trending"):
            if evergreen not in tags:
                tags.append(evergreen)
        return tags[:7]

    @staticmethod
    def _seo_score(primary: list[str], secondary: list[str], hashtags: list[str], intent: str) -> int:
        """Calculated 0-100 score from keyword breadth, long-tail depth and reach."""
        score = 30
        score += min(len(primary) * 6, 24)     # keyword breadth
        score += min(len(secondary) * 5, 20)   # long-tail coverage
        score += min(len(hashtags) * 2, 10)    # social/reach surface
        score += {"viral_discovery": 8, "commercial": 6, "informational": 5}[intent]
        return max(0, min(100, score))

    def analyze_and_optimize(self, bus: SharedMemoryBus, topic: str = None) -> dict:
        """Analyze a topic (top bus trend by default) and broadcast an SEO plan.

        Reads the top trend from ``bus.state["trends"]`` when no topic is
        explicitly passed, builds the keyword/intent/hook payload, broadcasts
        it as ``{"seo_strategy": seo_payload}`` from sender "SEO_Agent", and
        returns the payload.

        Args:
            bus: The shared memory bus to read trends from and broadcast to.
            topic: Optional explicit topic; defaults to the bus's top trend
                (or "Autonomous AI & Digital Media Growth" when no trend exists).

        Returns:
            The seo_payload dictionary (also stored on ``bus.state["seo_strategy"]``).
        """
        resolved_topic = (topic or "").strip() or self._resolve_topic(bus)

        primary = self._primary_keywords(resolved_topic)
        secondary = self._secondary_keywords(resolved_topic, primary)
        intent = self._search_intent(resolved_topic, primary)
        hook = self._viral_hook(resolved_topic, intent)
        hashtags = self._hashtags(primary)
        score = self._seo_score(primary, secondary, hashtags, intent)

        seo_payload: dict[str, Any] = {
            "topic": resolved_topic,
            "primary_keywords": primary,
            "secondary_keywords": secondary,
            "search_intent": intent,
            "viral_hook": hook,
            "hashtags": hashtags,
            "seo_score": score,
        }

        bus.broadcast(
            sender="SEO_Agent",
            message=(
                f"SEO plan for '{resolved_topic}': intent={intent}, "
                f"seo_score={score}/100, hook='{hook}'."
            ),
            data={"seo_strategy": seo_payload},
        )
        return seo_payload


if __name__ == "__main__":
    # Quick smoke test when executed directly.
    bus = SharedMemoryBus()
    bus.state["trends"] = {
        "Autonomous AI & Digital Media Growth": {"volume": "905K", "growth": "+38%"},
    }

    agent = SEOAgent()
    payload = agent.analyze_and_optimize(bus)

    # Bus state must be populated and the broadcast must be logged.
    assert bus.state["seo_strategy"], "seo_strategy was not populated on the bus"
    assert bus.state["seo_strategy"]["topic"] == "Autonomous AI & Digital Media Growth"
    assert any(m["sender"] == "SEO_Agent" for m in bus.state["messages"]), "no SEO_Agent message logged"
    assert payload["search_intent"] in ("viral_discovery", "informational", "commercial")
    assert 0 <= payload["seo_score"] <= 100
    assert payload["primary_keywords"] and payload["secondary_keywords"]
    assert payload["viral_hook"] and payload["hashtags"]

    # An explicit topic must override the bus trend.
    bus2 = SharedMemoryBus()
    explicit = agent.analyze_and_optimize(bus2, topic="Best Vegan Protein Powders")
    assert bus2.state["seo_strategy"]["topic"] == "Best Vegan Protein Powders"
    assert explicit["search_intent"] == "commercial"

    print("SEOAgent smoke test passed.")
    print(bus.to_json())
