from __future__ import annotations

import json
import time
from typing import Any

from brain_core.llm_router import ZeroBudgetLLMRouter
from brain_core.memory import SharedMemoryBus
from brain_core.multilingual import MultilingualTools
from brain_core.income_agents import OnlineIncomeResearchSwarm


class CEOBrain:
    AVAILABLE_ENGINE = {"groq", "gemini", "rule_based"}
    ZERO_BUDGET_MIN_SCORE = 55

    def __init__(
        self,
        llm_router: ZeroBudgetLLMRouter | None = None,
        multilingual: MultilingualTools | None = None,
        swarm: OnlineIncomeResearchSwarm | None = None,
        bus: SharedMemoryBus | None = None,
    ) -> None:
        self.router = llm_router or ZeroBudgetLLMRouter()
        self.multilingual = multilingual or MultilingualTools()
        self.swarm = swarm or OnlineIncomeResearchSwarm()
        self.bus = bus or SharedMemoryBus()
        self.last_directive: dict[str, Any] = {}

    def _llm_enrich(self, system_prompt: str, user_prompt: str) -> dict | None:
        data = self.router.generate_json(system_prompt, user_prompt)
        if data is None or not isinstance(data, dict):
            return None
        return data

    def _research(self, topic: str) -> list[dict[str, Any]]:
        return self.swarm.research()

    def _filter_viable(self, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in payload if r.get("seo_score", 0) >= self.ZERO_BUDGET_MIN_SCORE]

    def _build_directive(self, seo_payload: dict, viable: list[dict[str, Any]], language: str) -> dict[str, Any]:
        base = {
            "budget_status": "healthy",
            "budget_policy": "Balanced Growth - Organic + Boosted Viral Distribution",
            "sentiment": "positive",
            "content_tone": "Aspirational & Bold - Ride the Momentum",
            "format_choice": "VIDEO",
            "seo_score": seo_payload.get("seo_score", 0),
            "roi_score": 82,
            "expected_roi_index": 62,
            "sub_agent_priorities": {
                "seo_optimization": "HIGH",
                "content_creation": "HIGH",
                "compliance_check": "MEDIUM",
                "social_distribution": "CRITICAL",
            },
            "research_niches": viable,
            "language": language,
            "llm_engine": self.router.engines[0] if self.router.engines and self.router.engines[0] != "None" else "rule_based",
        }
        return base

    def _enforce_zero_budget(self, directive: dict) -> dict[str, Any]:
        directive["research_niches"] = self._filter_viable(directive.get("research_niches", []))
        if not directive["research_niches"]:
            directive["research_niches"] = self._research_directive_fallback()
        return directive

    @staticmethod
    def _research_directive_fallback() -> list[dict[str, Any]]:
        return [{"topic": "core brain", "seo_score": 60, "engine": "rule_based"}]

    def issue_directive(self, topic: str | None = None, language: str | None = None) -> dict[str, Any]:
        if topic:
            if language is None:
                language = self.multilingual.detect(topic)
        else:
            language = language or self.multilingual.detect("English")

        payload = {
            "topic": topic or "Autonomous AI & Digital Media Growth",
            "primary_keywords": ["ai", "digital", "media", "growth"],
            "secondary_keywords": ["ai tools", "content strategy", "video marketing"],
            "search_intent": "commercial",
            "viral_hook": "AI Content That Scales: The 2026 Blueprint",
            "hashtags": ["#AI", "#ContentStrategy", "#DigitalMarketing", "#Growth"],
            "seo_score": 72,
            "language": language,
        }

        self.bus.broadcast(
            sender="CEOBrain",
            message="Directorate call: zero-budget research and LLM routing",
            data={
                "seo_strategy": payload,
                "analytics": {"budget_status": "healthy", "sentiment": "positive", "best_format": "video", "roi_score": 82},
            },
        )

        viable = self._filter_viable(self._research(payload["topic"]))
        directive = self._build_directive(payload, viable, language)
        directive = self._enforce_zero_budget(directive)

        system_prompt = (
            "You are the Core Brain CEO. Reply with ONLY a JSON object with "
            "keys: executive_summary, headline, content_plan, next_actions."
        )
        user_prompt = (
            f"SEO strategy: {json.dumps(payload, ensure_ascii=False)}\n"
            f"Viable niches: {json.dumps(directive['research_niches'], ensure_ascii=False)}\n"
            "Produce the executive JSON object."
        )
        enriched = self._llm_enrich(system_prompt, user_prompt)
        if enriched is not None and isinstance(enriched, dict):
            directive["executive_summary"] = enriched.get("executive_summary", directive.get("executive_summary", ""))
            directive["headline"] = enriched.get("headline", directive.get("headline", ""))
            directive["content_plan"] = enriched.get("content_plan", directive.get("content_plan", []))
            directive["next_actions"] = enriched.get("next_actions", directive.get("next_actions", []))
            directive["llm_engine"] = self.router.engines[0] if self.router.engines and self.router.engines[0] != "None" else "rule_based"

        self.last_directive = directive
        self.bus.broadcast(
            sender="CEOBrain",
            message=f"Zero-budget directive issued: {directive['budget_status']} / {directive['format_choice']}",
            data={"ceo_directive": directive},
        )
        return directive

    def verbose(self) -> str:
        d = self.last_directive
        niche_names = ", ".join(n.get("topic", "?") for n in d.get("research_niches", [])) or "(none viable)"
        return (
            f"CEOBrain directive [{d.get('language', 'en')}] "
            f"budget={d.get('budget_status')} / tone={d.get('sentiment')} / "
            f"format={d.get('format_choice')} / engine={d.get('llm_engine')} | "
            f"ROI {d.get('expected_roi_index')}/100 | niches: {niche_names}"
        )
