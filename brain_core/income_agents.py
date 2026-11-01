from __future__ import annotations

import re
import time
from typing import Any

DEFAULT_TOPICS = {
    "blogging": "blogging",
    "affiliate_marketing": "affiliate marketing",
    "ecommerce_dropshipping": "e-commerce dropshipping",
    "freelancing": "freelancing online",
    "saas": "saas micro-SaaS",
    "youtube": "youtube content creation",
    "print_on_demand": "print on demand",
    "online_courses": "online courses",
    "digital_products": "digital products",
    "stock_photography": "stock photography",
}

INCOME_DOMAINS = tuple(DEFAULT_TOPICS)


class OnlineIncomeResearchSwarm:
    """Ten research agents over income domains."""

    def __init__(self, subjects: dict[str, str] | None = None) -> None:
        self.subjects = dict(DEFAULT_TOPICS)
        if subjects:
            self.subjects.update(subjects)
        self.results: list[dict[str, Any]] = []

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"[^\w\s\-'’]", " ", text).strip().lower()

    @staticmethod
    def _score(primary: list[str], secondary: list[str], intent: str) -> int:
        score = min(len(primary) * 6, 24) + min(len(secondary) * 5, 20)
        if intent == "viral_discovery":
            score += 8
        elif intent == "commercial":
            score += 6
        else:
            score += 5
        return max(0, min(100, score))

    @staticmethod
    def _intents(primary: list[str]) -> str:
        viral = {"viral", "trending", "exploding", "growth", "news", "share", "reel", "shorts", "watch"}
        commercial = {"best", "buy", "cheap", "price", "pricing", "deal", "deals", "review", "reviews"}
        primary_set = set(primary)
        if primary_set & viral:
            return "viral_discovery"
        if primary_set & commercial:
            return "commercial"
        return "informational"

    def _agent(self, topic: str) -> dict[str, Any]:
        cleaned = self._clean(topic)
        primary = self._clean(cleaned).split()[:4]
        year = time.strftime("%Y")
        secondary = [
            f"best {cleaned} tools",
            f"how {cleaned} works",
            f"top {cleaned} trends {year}",
            f"{cleaned} examples and results",
        ]
        hook = f"{cleaned.capitalize()} Explained: The Definitive Guide for {year}"
        hashtags = [f"#{word.upper() if len(word) <= 2 else word.title()}" for word in primary[:4]]
        hashtags += ["#SEO", "#ContentStrategy", "#Trending"]
        return {
            "topic": cleaned,
            "primary_keywords": primary,
            "secondary_keywords": secondary,
            "search_intent": self._intents(primary),
            "viral_hook": hook,
            "hashtags": hashtags,
            "seo_score": self._score(primary, secondary, self._intents(primary)),
        }

    def research(self, override: dict[str, str] | None = None) -> list[dict[str, Any]]:
        subjects = dict(self.subjects)
        if override:
            subjects.update(override)
        self.results = []
        for domain, topic in subjects.items():
            result = self._agent(topic)
            result["domain"] = domain
            self.results.append(result)
            time.sleep(0.05)
        return list(self.results)

    def viable(self, min_roi_score: int = 55) -> list[dict[str, Any]]:
        return [r for r in self.results if r.get("seo_score", 0) >= min_roi_score]

    def top_n(self, n: int = 3) -> list[dict[str, Any]]:
        ranked = sorted(self.results, key=lambda r: r["seo_score"], reverse=True)
        return ranked[:n]
