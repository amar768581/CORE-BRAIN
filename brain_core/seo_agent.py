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
