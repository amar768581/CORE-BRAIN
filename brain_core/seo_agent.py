"""SEOAgent: keyword research and viral content optimization on the SharedMemoryBus.

The agent derives its topic from the top trend on the bus (or an explicitly
passed topic), then produces a JSON-serializable SEO payload — primary
keywords, long-tail keywords, search intent, a viral hook, hashtags and a
0-100 seo_score — and broadcasts it back onto the bus for the other agents.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

try:  # Package execution (import brain_core.seo_agent).
    from brain_core.memory_bus import SharedMemoryBus
    from brain_core.llm_client import LLMClient
except ModuleNotFoundError:  # Direct execution: python3 brain_core/seo_agent.py
    from memory_bus import SharedMemoryBus
    from llm_client import LLMClient

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

_LLM_INTENTS = {"viral_discovery", "commercial", "informational"}


def _str_list(value: Any, limit: int = 8) -> list[str]:
    """Coerce an LLM list-of-strings field into a clean, bounded list."""
    if not isinstance(value, list):
        return []
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:limit]


class SEOAgent:
    """Produces SEO/viral-optimization payloads from trends on the shared bus."""

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        """Use an injected LLMClient, or a default one reading the env keys."""
        self.llm = llm if llm is not None else LLMClient()

    def _llm_enrich(self, topic: str, rule_payload: dict) -> Optional[dict]:
        """Ask the LLM for SEO insights and merge valid fields into the payload.

        Returns a merged copy of the rule-based payload when the model supplies
        usable insights, otherwise None so the caller keeps the deterministic
        result. The topic itself is never delegated to the model.
        """
        system_prompt = (
            "You are an expert SEO and viral-content strategist. Reply with ONLY a "
            "JSON object (no prose, no markdown fences) with these keys: "
            "primary_keywords (array of strings), secondary_keywords (array of "
            "long-tail strings), search_intent (one of viral_discovery, commercial, "
            "informational), viral_hook (string), hashtags (array of strings)."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Current rule-based plan: {json.dumps(rule_payload, ensure_ascii=False)}\n"
            "Produce an improved SEO plan for this topic as the JSON object described."
        )
        data = self.llm.generate_json(system_prompt, user_prompt)
        if not isinstance(data, dict):
            return None

        merged = dict(rule_payload)
        primary = _str_list(data.get("primary_keywords"))
        if primary:
            merged["primary_keywords"] = primary
        secondary = _str_list(data.get("secondary_keywords"))
        if secondary:
            merged["secondary_keywords"] = secondary
        intent = str(data.get("search_intent") or "").strip().lower()
        if intent in _LLM_INTENTS:
            merged["search_intent"] = intent
        hook = str(data.get("viral_hook") or "").strip()
        if hook:
            merged["viral_hook"] = hook
        hashtags = _str_list(data.get("hashtags"), limit=7)
        if hashtags:
            merged["hashtags"] = [
                tag if tag.startswith("#") else "#" + tag for tag in hashtags
            ]

        if merged == rule_payload:
            return None  # Nothing usable came back; stay rule-based.

        # Keep the 0-100 score consistent with the merged keyword set.
        merged["seo_score"] = self._seo_score(
            merged["primary_keywords"],
            merged["secondary_keywords"],
            merged["hashtags"],
            merged["search_intent"],
        )
        return merged

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

        # Optional LLM enrichment; any failure keeps the rule-based payload.
        enriched = self._llm_enrich(resolved_topic, seo_payload)
        if enriched is not None:
            seo_payload = enriched
            seo_payload["engine"] = "llm"
        else:
            seo_payload["engine"] = "rule_based"

        bus.broadcast(
            sender="SEO_Agent",
            message=(
                f"SEO plan for '{resolved_topic}' ({seo_payload['engine']} engine): "
                f"intent={seo_payload['search_intent']}, "
                f"seo_score={seo_payload['seo_score']}/100, "
                f"hook='{seo_payload['viral_hook']}'."
            ),
            data={"seo_strategy": seo_payload},
        )
        return seo_payload


if __name__ == "__main__":
    # Quick smoke test when executed directly. Provider keys are popped so the
    # rule-based path stays deterministic regardless of the host environment.
    import os

    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)

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
    assert payload["engine"] == "rule_based", "no key => rule_based engine"

    # An explicit topic must override the bus trend.
    bus2 = SharedMemoryBus()
    explicit = agent.analyze_and_optimize(bus2, topic="Best Vegan Protein Powders")
    assert bus2.state["seo_strategy"]["topic"] == "Best Vegan Protein Powders"
    assert explicit["search_intent"] == "commercial"
    assert explicit["engine"] == "rule_based"

    # --- LLM path: a mocked provider enriches and marks the payload -------
    class _FakeLLM:
        def __init__(self, response):
            self.response = response

        def generate_json(self, system_prompt, user_prompt):
            return self.response

    bus3 = SharedMemoryBus()
    llm_payload = SEOAgent(llm=_FakeLLM({
        "primary_keywords": ["ai video editor", "auto captions"],
        "secondary_keywords": ["best ai video editor free"],
        "search_intent": "commercial",
        "viral_hook": "I Edited This Video in 60 Seconds With AI",
        "hashtags": ["AIVideo", "#ContentCreation"],
    })).analyze_and_optimize(bus3, topic="AI Video Editing Tools")
    assert llm_payload["engine"] == "llm"
    assert llm_payload["primary_keywords"] == ["ai video editor", "auto captions"]
    assert llm_payload["search_intent"] == "commercial"
    assert llm_payload["viral_hook"] == "I Edited This Video in 60 Seconds With AI"
    assert llm_payload["hashtags"][0] == "#AIVideo"  # missing # added back
    assert 0 <= llm_payload["seo_score"] <= 100
    assert bus3.state["seo_strategy"]["engine"] == "llm"

    # --- Fallback: unusable model output keeps the rule-based payload ------
    bus4 = SharedMemoryBus()
    fallback = SEOAgent(llm=_FakeLLM({"unrelated": "keys"})).analyze_and_optimize(
        bus4, topic="AI Video Editing Tools"
    )
    assert fallback["engine"] == "rule_based"
    assert fallback == bus4.state["seo_strategy"]

    print("SEOAgent smoke test passed.")
    print(bus.to_json())
