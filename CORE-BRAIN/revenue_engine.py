"""CORE-BRAIN revenue engine.

Three revenue-focused agents behind one interface:

* Growth Lead        - ICE-scored experiments, funnel diagnostics, channel budget.
* Solutions Engineer - requirement fit, integration phasing, demo scripts.
* SEO Team           - keyword opportunities, on-page audits, content briefs.

Standard library only. The directory name is hyphenated, so import it with::

    import sys; sys.path.append("CORE-BRAIN")
    import revenue_engine

or run ``python CORE-BRAIN/revenue_engine.py`` for a demo.
"""

from __future__ import annotations

import csv
import math
import re
from collections.abc import Mapping as _MappingABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "AgentOutput",
    "BaseAgent",
    "GrowthLeadAgent",
    "SolutionsEngineerAgent",
    "SEOAgent",
    "RevenueEngine",
]

_STOPWORDS = frozenset(
    {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}
)


# --------------------------------------------------------------------------- #
# Shared plumbing
# --------------------------------------------------------------------------- #
@dataclass
class AgentOutput:
    """Structured result returned by every agent action."""

    agent: str
    role: str
    action: str
    summary: str
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        """Plain-text report suitable for terminals and logs."""
        lines = [f"{self.agent} :: {self.action}", f"  {self.summary}"]
        for rec in self.recommendations:
            lines.append(f"  - {rec.get('detail', rec)}")
        if self.metrics:
            stats = ", ".join(f"{k}={v}" for k, v in self.metrics.items())
            lines.append(f"  metrics: {stats}")
        return "\n".join(lines)


def _require_rows(
    key: str, payload: Mapping[str, Any], fields: Sequence[str]
) -> list[Mapping[str, Any]]:
    """Validate that payload[key] is a non-empty list of mappings with fields."""
    rows = payload.get(key)
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError(f"payload['{key}'] must be a non-empty list")
    checked: list[Mapping[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, _MappingABC):
            raise ValueError(f"payload['{key}'][{index}] must be a mapping")
        missing = [f for f in fields if f not in row]
        if missing:
            label = row.get("name") or row.get("term") or index
            raise ValueError(
                f"payload['{key}'][{index}] ({label}) missing: {', '.join(missing)}"
            )
        checked.append(row)
    return checked


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if w not in _STOPWORDS
    )


class BaseAgent:
    """Common contract: map a free-text task (or a payload) onto an action.

    Subclasses declare ``ACTIONS`` mapping action name -> spec with
    ``triggers`` (substrings matched against the task), ``requires``
    (payload keys the action needs) and ``handler`` (method name).
    """

    name: str = "Agent"
    role: str = ""
    mission: str = ""
    ACTIONS: dict[str, dict[str, Any]] = {}

    def describe(self) -> dict[str, str]:
        return {
            "name": self.name,
            "role": self.role,
            "mission": self.mission,
            "actions": ", ".join(self.ACTIONS),
        }

    def run(self, task: str, payload: Mapping[str, Any] | None = None) -> AgentOutput:
        """Route a free-text task to an action and return its output."""
        payload = dict(payload or {})
        action = self._resolve(task, payload)
        return self._invoke(action, payload)

    def run_all(self, payload: Mapping[str, Any] | None = None) -> AgentOutput:
        """Run every action the payload has data for and combine the results."""
        payload = dict(payload or {})
        runnable = [
            action
            for action, spec in self.ACTIONS.items()
            if all(key in payload for key in spec["requires"])
        ]
        if not runnable:
            needed = "; ".join(
                f"{action} needs {', '.join(spec['requires'])}"
                for action, spec in self.ACTIONS.items()
            )
            raise ValueError(f"{self.name}: payload matches no action ({needed})")
        outputs = [self._invoke(action, payload) for action in runnable]
        if len(outputs) == 1:
            return outputs[0]
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action=" + ".join(runnable),
            summary=" | ".join(o.summary for o in outputs),
            recommendations=[r for o in outputs for r in o.recommendations],
            metrics={action: o.metrics for action, o in zip(runnable, outputs)},
        )

    def _resolve(self, task: str, payload: Mapping[str, Any]) -> str:
        text = task.lower()
        matched = [
            action
            for action, spec in self.ACTIONS.items()
            if any(trigger in text for trigger in spec["triggers"])
        ]
        if not matched:
            options = ", ".join(
                f"{action} ({'/'.join(spec['triggers'])})"
                for action, spec in self.ACTIONS.items()
            )
            raise ValueError(f"{self.name} cannot map task {task!r}; try: {options}")
        # Prefer a matched action this payload can actually feed; otherwise fall
        # back to the first match so the missing-keys error names a real action.
        for action in matched:
            if all(key in payload for key in self.ACTIONS[action]["requires"]):
                return action
        return matched[0]

    def _invoke(self, action: str, payload: Mapping[str, Any]) -> AgentOutput:
        spec = self.ACTIONS[action]
        missing = [key for key in spec["requires"] if key not in payload]
        if missing:
            raise ValueError(
                f"{self.name}.{action} needs payload keys: {', '.join(missing)}"
            )
        output = getattr(self, spec["handler"])(payload)
        if not isinstance(output, AgentOutput):
            raise TypeError(f"{self.name}.{action} must return AgentOutput")
        return output


# --------------------------------------------------------------------------- #
# Growth Lead
# --------------------------------------------------------------------------- #
class GrowthLeadAgent(BaseAgent):
    """Owns acquisition, activation and monetisation experiments."""

    name = "Growth Lead"
    role = "Acquisition, activation and monetisation strategy"
    mission = "Turn a pipeline target into prioritised experiments and channel spend."

    ACTIONS: dict[str, dict[str, Any]] = {
        "experiments": {
            "triggers": ("experiment", "ice", "backlog", "priorit"),
            "requires": ("experiments",),
            "handler": "_score_experiments",
        },
        "funnel": {
            "triggers": ("funnel", "conversion", "drop-off", "dropoff", "leak"),
            "requires": ("funnel",),
            "handler": "_analyze_funnel",
        },
        "channels": {
            "triggers": ("channel", "budget", "cac", "roas", "spend", "acquisition"),
            "requires": ("channels",),
            "handler": "_prioritize_channels",
        },
    }

    def _score_experiments(self, payload: Mapping[str, Any]) -> AgentOutput:
        rows = _require_rows(
            "experiments", payload, ("name", "impact", "confidence", "ease")
        )
        scored: list[dict[str, Any]] = []
        for row in rows:
            try:
                impact, confidence, ease = (
                    float(row["impact"]),
                    float(row["confidence"]),
                    float(row["ease"]),
                )
            except (TypeError, ValueError):
                raise ValueError(
                    f"experiment {row['name']!r} needs numeric impact/confidence/ease"
                ) from None
            ice = round((impact + confidence + ease) / 3.0, 1)
            scored.append({**row, "ice": ice})
        scored.sort(key=lambda r: r["ice"], reverse=True)

        recommendations = []
        for rank, row in enumerate(scored, 1):
            recommendations.append(
                {
                    "rank": rank,
                    "name": row["name"],
                    "ice": row["ice"],
                    "detail": f"#{rank} {row['name']} - ICE {row['ice']}",
                    "next_step": row.get(
                        "next_step",
                        "Scope a one-week test and define its success metric.",
                    ),
                }
            )
        average = round(sum(r["ice"] for r in scored) / len(scored), 1)
        top = scored[0]
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="experiments",
            summary=(
                f"Scored {len(scored)} experiments (avg ICE {average}); "
                f"run '{top['name']}' first at ICE {top['ice']}."
            ),
            recommendations=recommendations,
            metrics={
                "scored": len(scored),
                "average_ice": average,
                "top_experiment": top["name"],
            },
        )

    def _analyze_funnel(self, payload: Mapping[str, Any]) -> AgentOutput:
        funnel = payload["funnel"]
        if isinstance(funnel, _MappingABC):
            stages = list(funnel.items())
        else:
            stages = [tuple(item) for item in funnel]  # type: ignore[misc]
        if len(stages) < 2:
            raise ValueError("funnel needs at least two stages")
        for stage, count in stages:
            if not isinstance(count, (int, float)) or count < 0:
                raise ValueError(f"funnel stage {stage!r} needs a non-negative count")

        steps: list[dict[str, Any]] = []
        previous_name = None
        previous_count = None
        for stage, count in stages:
            if previous_count is None:
                conversion = 100.0
            elif previous_count:
                conversion = count / previous_count * 100.0
            else:
                conversion = 0.0
            steps.append(
                {
                    "stage": stage,
                    "count": count,
                    "from_stage": previous_name,
                    "step_conversion": round(conversion, 1),
                }
            )
            previous_name, previous_count = stage, count

        entered, converted = stages[0][1], stages[-1][1]
        overall = round(converted / entered * 100.0, 1) if entered else 0.0
        leak = min(steps[1:], key=lambda s: s["step_conversion"])

        recommendations: list[dict[str, Any]] = [
            {
                "stage": leak["stage"],
                "detail": (
                    f"Largest leak: {leak['stage']} keeps only "
                    f"{leak['step_conversion']}% of {leak['from_stage']}"
                ),
                "fix": "Instrument this step and run one activation experiment this sprint.",
            }
        ]
        for step in sorted(steps[1:], key=lambda s: s["step_conversion"]):
            recommendations.append(
                {
                    "stage": step["stage"],
                    "detail": (
                        f"{step['stage']}: {step['count']:,} "
                        f"({step['step_conversion']}% from {step['from_stage']})"
                    ),
                }
            )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="funnel",
            summary=(
                f"{entered:,} entered, {converted:,} converted ({overall}% overall); "
                f"weakest step is {leak['stage']} at {leak['step_conversion']}%."
            ),
            recommendations=recommendations,
            metrics={
                "entered": entered,
                "converted": converted,
                "overall_conversion": overall,
                "leakiest_stage": leak["stage"],
            },
        )

    def _prioritize_channels(self, payload: Mapping[str, Any]) -> AgentOutput:
        rows = _require_rows("channels", payload, ("name", "spend"))
        if len(rows) < 2:
            raise ValueError("channels needs at least two channels to compare")
        has_revenue = all("revenue" in r for r in rows)
        has_customers = all("customers" in r for r in rows)
        if not (has_revenue or has_customers):
            raise ValueError(
                "channels need 'revenue' or 'customers' alongside 'spend'"
            )

        channels: list[dict[str, Any]] = []
        for row in rows:
            try:
                spend = float(row["spend"])
            except (TypeError, ValueError):
                raise ValueError(f"channel {row['name']!r} needs a numeric spend") from None
            if spend <= 0:
                raise ValueError(f"channel {row['name']!r} spend must be positive")
            channel = {**row, "spend": spend}
            if has_revenue:
                channel["roas"] = round(float(row["revenue"]) / spend, 2)
            if has_customers:
                channel["cac"] = round(spend / float(row["customers"]), 2)
            channels.append(channel)

        metric_name = "roas" if has_revenue else "cac"
        ranked = sorted(channels, key=lambda c: c[metric_name], reverse=has_revenue)

        def metric(channel: Mapping[str, Any]) -> str:
            if metric_name == "roas":
                return f"ROAS {channel['roas']}x"
            return f"CAC ${channel['cac']:,.0f}"

        best_desc = metric(ranked[0])
        worst_desc = metric(ranked[-1])

        best, worst = ranked[0], ranked[-1]
        shift = round(worst["spend"] * 0.15)
        recommendations: list[dict[str, Any]] = [
            {
                "channel": best["name"],
                "action": "scale",
                "detail": f"Scale {best['name']} - {best_desc}",
            },
            {
                "channel": worst["name"],
                "action": "cut-or-retest",
                "detail": f"Cut or re-test {worst['name']} - {worst_desc}",
            },
            {
                "channel": worst["name"],
                "action": "reallocate",
                "detail": (
                    f"Move ~15% of {worst['name']} spend (${shift:,.0f}) to "
                    f"{best['name']} and re-measure in two weeks"
                ),
            },
        ]
        for channel in ranked[1:-1]:
            desc = metric(channel)
            recommendations.append(
                {
                    "channel": channel["name"],
                    "action": "hold",
                    "detail": f"Hold {channel['name']} at current budget - {desc}",
                }
            )

        metrics: dict[str, Any] = {
            "best_channel": best["name"],
            "worst_channel": worst["name"],
            "total_spend": sum(c["spend"] for c in channels),
        }
        if has_customers:
            total_customers = sum(float(c["customers"]) for c in channels)
            if total_customers:
                metrics["blended_cac"] = round(
                    metrics["total_spend"] / total_customers, 2
                )
        summary = (
            f"{best['name']} leads ({best_desc}); {worst['name']} trails "
            f"({worst_desc}); rebalance ~15% of spend."
        )
        if "blended_cac" in metrics:
            summary += f" Blended CAC ${metrics['blended_cac']:,.0f}."
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="channels",
            summary=summary,
            recommendations=recommendations,
            metrics=metrics,
        )


# --------------------------------------------------------------------------- #
# Solutions Engineer
# --------------------------------------------------------------------------- #
class SolutionsEngineerAgent(BaseAgent):
    """Owns technical fit, integration planning and customer demos."""

    name = "Solutions Engineer"
    role = "Technical pre-sales and implementation planning"
    mission = "Prove the product fits, sequence the integration work, land the demo."

    ACTIONS: dict[str, dict[str, Any]] = {
        "fit": {
            "triggers": ("fit", "requirement", "rfp", "capability", "coverage", "gap"),
            "requires": ("requirements", "capabilities"),
            "handler": "_assess_fit",
        },
        "integrations": {
            "triggers": ("integration", "implementation", "effort", "plan"),
            "requires": ("integrations",),
            "handler": "_plan_integrations",
        },
        "demo": {
            "triggers": ("demo", "discovery", "call", "presentation", "pitch"),
            "requires": ("persona",),
            "handler": "_build_demo_script",
        },
    }

    _WEIGHTS = {"must": 3, "should": 2, "could": 1}

    def _assess_fit(self, payload: Mapping[str, Any]) -> AgentOutput:
        requirements = _require_rows("requirements", payload, ("name",))
        raw_capabilities = payload["capabilities"]
        if not isinstance(raw_capabilities, (list, tuple)) or not raw_capabilities:
            raise ValueError("payload['capabilities'] must be a non-empty list")
        capabilities = [
            _tokens(str(cap)) for cap in raw_capabilities if _tokens(str(cap))
        ]
        if not capabilities:
            raise ValueError("payload['capabilities'] has no usable entries")

        met_weight = total_weight = 0
        blockers: list[str] = []
        recommendations: list[dict[str, Any]] = []
        for req in requirements:
            name = str(req["name"])
            priority = str(req.get("priority", "should")).lower()
            weight = self._WEIGHTS.get(priority, 2)
            total_weight += weight
            req_tokens = _tokens(name)
            covered = bool(req_tokens) and any(
                req_tokens <= cap or cap <= req_tokens for cap in capabilities
            )
            if covered:
                met_weight += weight
                status = "covered"
            else:
                status = "BLOCKER" if priority == "must" else "gap"
                if priority == "must":
                    blockers.append(name)
            recommendations.append(
                {
                    "requirement": name,
                    "priority": priority,
                    "covered": covered,
                    "detail": f"[{priority}] {name}: {status}",
                }
            )
        if blockers:
            recommendations.insert(
                0,
                {
                    "requirement": ", ".join(blockers),
                    "priority": "must",
                    "covered": False,
                    "detail": (
                        f"{len(blockers)} must-have gap(s) block the deal: "
                        f"{', '.join(blockers)}"
                    ),
                },
            )
        score = round(100.0 * met_weight / total_weight, 1) if total_weight else 0.0
        summary = (
            f"Fit score {score}% across {len(requirements)} requirements; "
            f"{len(blockers)} blocking must-have gap(s)."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="fit",
            summary=summary,
            recommendations=recommendations,
            metrics={
                "fit_score": score,
                "requirements": len(requirements),
                "blockers": len(blockers),
            },
        )

    _EFFORT_DAYS = {"s": 2, "m": 5, "l": 10}
    _PHASES = (
        ("must", "Phase 1 (must-have)"),
        ("should", "Phase 2 (should-have)"),
        ("could", "Phase 3 (nice-to-have)"),
    )

    def _plan_integrations(self, payload: Mapping[str, Any]) -> AgentOutput:
        rows = _require_rows("integrations", payload, ("name",))
        phase_by_priority = dict(self._PHASES)
        phase_order = {priority: i for i, (priority, _) in enumerate(self._PHASES)}

        items: list[dict[str, Any]] = []
        for row in rows:
            name = str(row["name"])
            effort = str(row.get("effort", "m")).strip().lower()
            if "days" in row:
                try:
                    days = int(row["days"])
                except (TypeError, ValueError):
                    raise ValueError(f"integration {name!r}: 'days' must be an integer") from None
            elif effort in self._EFFORT_DAYS:
                days = self._EFFORT_DAYS[effort]
            else:
                raise ValueError(
                    f"integration {name!r}: effort must be S/M/L or provide 'days'"
                )
            if days <= 0:
                raise ValueError(f"integration {name!r}: effort must be positive")
            priority = str(row.get("priority", "should")).lower()
            items.append(
                {
                    **row,
                    "days": days,
                    "priority": priority,
                    "phase": phase_by_priority.get(
                        priority, phase_by_priority["should"]
                    ),
                }
            )
        items.sort(
            key=lambda item: (
                phase_order.get(item["priority"], 1),
                item["days"],
                str(item["name"]).lower(),
            )
        )

        recommendations = [
            {
                "integration": item["name"],
                "phase": item["phase"],
                "days": item["days"],
                "detail": (
                    f"{item['phase']}: {item['name']} - {item['days']}d "
                    f"(effort {str(item.get('effort', '?')).upper()})"
                ),
            }
            for item in items
        ]
        total_days = sum(item["days"] for item in items)
        longest = max(items, key=lambda item: item["days"])
        phases_used = len({item["phase"] for item in items})
        summary = (
            f"{len(items)} integrations sequenced into {phases_used} phases; "
            f"{total_days} engineering-days total, longest pole "
            f"{longest['name']} at {longest['days']}d."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="integrations",
            summary=summary,
            recommendations=recommendations,
            metrics={
                "integrations": len(items),
                "total_days": total_days,
                "longest_pole": f"{longest['name']} ({longest['days']}d)",
                "phases": phases_used,
            },
        )

    def _build_demo_script(self, payload: Mapping[str, Any]) -> AgentOutput:
        persona = str(payload["persona"]).strip()
        if not persona:
            raise ValueError("payload['persona'] must be a non-empty string")
        points = [str(p) for p in payload.get("value_points", []) if str(p).strip()]
        if not points:
            points = ["core workflow", "reporting", "integrations"]
        try:
            duration = int(payload.get("duration_minutes", 45))
        except (TypeError, ValueError):
            raise ValueError("duration_minutes must be an integer") from None
        if duration < 10:
            raise ValueError("duration_minutes must be at least 10")

        questions = [
            f"What does your current {persona} workflow look like today?",
            "Which step costs the most time or creates the most rework?",
            "What would make this quarter a clear win for your team?",
        ]
        segments = [
            ("Discovery", round(duration * 0.10), "Ask: " + "; ".join(questions)),
            (
                "Problem framing",
                round(duration * 0.10),
                f"Connect {points[0]} to the pain the {persona} just described.",
            ),
            (
                "Live demo",
                round(duration * 0.50),
                "Show " + "; ".join(points) + " in one realistic scenario.",
            ),
            (
                "Technical Q&A",
                round(duration * 0.20),
                "Cover API, SSO and security; log unknowns as follow-ups.",
            ),
            (
                "Next steps",
                round(duration * 0.10),
                "Confirm success criteria, pilot scope and a deep-dive date.",
            ),
        ]
        minutes = [max(1, m) for _, m, _ in segments]
        minutes[2] += duration - sum(minutes)  # live demo absorbs rounding drift
        if minutes[2] < 1:
            raise ValueError("duration_minutes too small to build an agenda")

        recommendations: list[dict[str, Any]] = []
        clock = 0
        for (name, _, talk_track), mins in zip(segments, minutes):
            window = f"{clock}-{clock + mins} min"
            clock += mins
            recommendations.append(
                {
                    "segment": name,
                    "window": window,
                    "topic": name,
                    "detail": f"{window} {name}: {talk_track}",
                }
            )
        summary = (
            f"{duration}-minute {persona} demo in {len(recommendations)} segments; "
            f"anchor the live demo on {', '.join(points)}."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="demo",
            summary=summary,
            recommendations=recommendations,
            metrics={
                "duration_minutes": duration,
                "segments": len(recommendations),
                "value_points": len(points),
            },
        )


# --------------------------------------------------------------------------- #
# SEO Team
# --------------------------------------------------------------------------- #
class SEOAgent(BaseAgent):
    """Owns keyword opportunities, on-page audits and content briefs."""

    name = "SEO Team"
    role = "Organic acquisition through keywords and content"
    mission = "Find the keywords worth winning and ship pages that rank for them."

    ACTIONS: dict[str, dict[str, Any]] = {
        "keywords": {
            "triggers": ("keyword", "serp", "ranking", "rank ", "opportunity"),
            "requires": ("keywords",),
            "handler": "_score_keywords",
        },
        "audit": {
            "triggers": ("audit", "on-page", "onpage", "meta", "title tag", "thin content"),
            "requires": ("page",),
            "handler": "_audit_page",
        },
        "brief": {
            "triggers": ("brief", "content", "article", "blog", "outline"),
            "requires": ("keyword",),
            "handler": "_build_content_brief",
        },
    }

    _INTENT_WEIGHT = {
        "transactional": 1.5,
        "commercial": 1.25,
        "navigational": 1.0,
        "informational": 0.75,
    }

    def _score_keywords(self, payload: Mapping[str, Any]) -> AgentOutput:
        rows = _require_rows(
            "keywords", payload, ("term", "monthly_volume", "difficulty")
        )
        scored: list[dict[str, Any]] = []
        for row in rows:
            try:
                volume = int(row["monthly_volume"])
                difficulty = float(row["difficulty"])
            except (TypeError, ValueError):
                raise ValueError(
                    f"keyword {row['term']!r} needs numeric monthly_volume/difficulty"
                ) from None
            if volume < 0 or not 0 <= difficulty <= 100:
                raise ValueError(
                    f"keyword {row['term']!r}: volume >= 0 and difficulty 0-100"
                )
            intent = str(row.get("intent", "informational")).lower()
            weight = self._INTENT_WEIGHT.get(intent, 1.0)
            volume_score = min(100.0, 20.0 * math.log10(volume + 1))
            opportunity = round(
                min(100.0, volume_score * weight * (100.0 - difficulty) / 100.0), 1
            )
            rank = row.get("current_rank")
            scored.append(
                {
                    **row,
                    "intent": intent,
                    "volume_score": round(volume_score, 1),
                    "opportunity": opportunity,
                    "quick_win": difficulty < 30 and volume_score >= 40,
                    "striking_distance": isinstance(rank, (int, float))
                    and 11 <= rank <= 20,
                }
            )
        scored.sort(key=lambda r: r["opportunity"], reverse=True)

        recommendations: list[dict[str, Any]] = []
        for index, row in enumerate(scored, 1):
            tags = ""
            if row["quick_win"]:
                tags += " [quick win]"
            if row["striking_distance"]:
                tags += " [striking distance]"
            recommendations.append(
                {
                    "rank": index,
                    "term": row["term"],
                    "opportunity": row["opportunity"],
                    "detail": (
                        f"#{index} {row['term']} - opportunity "
                        f"{row['opportunity']}/100 (KD {row['difficulty']:.0f}, "
                        f"{row['monthly_volume']:,}/mo, {row['intent']}){tags}"
                    ),
                }
            )
        quick_wins = sum(1 for r in scored if r["quick_win"])
        top = scored[0]
        summary = (
            f"{len(scored)} keywords scored; best bet '{top['term']}' at "
            f"{top['opportunity']}/100 with {quick_wins} quick win(s)."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="keywords",
            summary=summary,
            recommendations=recommendations,
            metrics={
                "scored": len(scored),
                "top_keyword": top["term"],
                "quick_wins": quick_wins,
            },
        )

    def _audit_page(self, payload: Mapping[str, Any]) -> AgentOutput:
        page = payload["page"]
        if not isinstance(page, _MappingABC):
            raise ValueError("payload['page'] must be a mapping")
        required = ("title", "meta_description", "h1", "word_count", "internal_links")
        missing = [key for key in required if key not in page]
        if missing:
            raise ValueError(f"page missing keys: {', '.join(missing)}")

        checks: list[dict[str, Any]] = []

        def add(check: str, passed: bool, ok: str, fix: str) -> None:
            checks.append(
                {
                    "check": check,
                    "passed": bool(passed),
                    "detail": (
                        f"PASS - {check}: {ok}" if passed else f"FAIL - {check}: {fix}"
                    ),
                }
            )

        title = str(page["title"])
        add(
            "title tag",
            30 <= len(title) <= 60,
            f"{len(title)} chars",
            f"{len(title)} chars - rewrite to 30-60 characters",
        )
        meta = str(page["meta_description"])
        add(
            "meta description",
            70 <= len(meta) <= 160,
            f"{len(meta)} chars",
            f"{len(meta)} chars - rewrite to 70-160 characters",
        )
        h1s = page["h1"]
        h1_list = [h1s] if isinstance(h1s, str) else list(h1s)
        add(
            "single H1",
            len(h1_list) == 1,
            f"{len(h1_list)} H1",
            f"{len(h1_list)} H1 tags - keep exactly one",
        )
        word_count = int(page["word_count"])
        add(
            "content depth",
            word_count >= 300,
            f"{word_count} words",
            f"{word_count} words - expand to at least 300 words",
        )
        internal_links = int(page["internal_links"])
        add(
            "internal links",
            internal_links >= 3,
            f"{internal_links} links",
            f"{internal_links} links - add at least 3 internal links",
        )
        if "images" in page:
            images = list(page["images"])
            no_alt = [img for img in images if not str(img.get("alt", "")).strip()]
            add(
                "image alt text",
                not no_alt,
                f"{len(images)} images all described",
                f"{len(no_alt)} image(s) missing alt text",
            )
        if "https" in page:
            add(
                "HTTPS",
                bool(page["https"]),
                "served over HTTPS",
                "page is not served over HTTPS - enable TLS",
            )
        if "mobile_ready" in page:
            add(
                "mobile ready",
                bool(page["mobile_ready"]),
                "renders on mobile",
                "page is not mobile friendly - fix viewport and layout",
            )
        if "schema_markup" in page:
            add(
                "structured data",
                bool(page["schema_markup"]),
                "markup present",
                "no structured data - add Schema.org markup",
            )

        failed = [c for c in checks if not c["passed"]]
        passed_count = len(checks) - len(failed)
        score = round(100.0 * passed_count / len(checks), 1)
        top_issue = failed[0]["check"] if failed else "none"
        summary = (
            f"On-page score {score}% ({passed_count}/{len(checks)} checks passed); "
            f"top issue: {top_issue}."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="audit",
            summary=summary,
            recommendations=failed + [c for c in checks if c["passed"]],
            metrics={
                "score": score,
                "passed": passed_count,
                "failed": len(failed),
                "checks": len(checks),
            },
        )

    def _build_content_brief(self, payload: Mapping[str, Any]) -> AgentOutput:
        keyword = str(payload["keyword"]).strip()
        if not keyword:
            raise ValueError("payload['keyword'] must be a non-empty string")
        try:
            difficulty = float(payload.get("difficulty", 50))
        except (TypeError, ValueError):
            raise ValueError("difficulty must be numeric (0-100)") from None
        audience = str(payload.get("audience", "practitioners searching this topic"))
        related = [str(t) for t in payload.get("related_terms", []) if str(t).strip()]

        target_words = 2000 if difficulty >= 60 else 1500
        title = f"{keyword}: The Complete Guide"
        if len(title) > 60:
            title = f"{keyword} Guide"[:57] + "..."
        meta = (
            f"Learn {keyword} end to end: what it is, why it matters and how to "
            f"put it to work. Practical steps for {audience}."
        )[:160]

        outline = [
            f"What is {keyword}?",
            f"Why {keyword} matters for {audience}",
            f"How to apply {keyword}: a step-by-step playbook",
            "Tools, templates and real examples",
            f"{keyword}: mistakes to avoid",
            f"{keyword}: frequently asked questions",
        ]
        questions = [
            f"what is {keyword}",
            f"how to {keyword}",
            f"{keyword} examples",
        ] + related[:5]

        recommendations: list[dict[str, Any]] = [
            {"element": "title", "detail": f"Title tag ({len(title)} chars): {title}"},
            {
                "element": "meta",
                "detail": f"Meta description ({len(meta)} chars): {meta}",
            },
        ]
        for index, heading in enumerate(outline, 1):
            recommendations.append(
                {"element": "h2", "detail": f"H2 #{index}: {heading}"}
            )
        if related:
            recommendations.append(
                {
                    "element": "secondary terms",
                    "detail": "Work in secondary terms: " + ", ".join(related),
                }
            )
        summary = (
            f"Brief for '{keyword}': {len(outline)} sections, {target_words} words "
            f"targeted at difficulty {difficulty:.0f}."
        )
        return AgentOutput(
            agent=self.name,
            role=self.role,
            action="brief",
            summary=summary,
            recommendations=recommendations,
            metrics={
                "target_words": target_words,
                "sections": len(outline),
                "secondary_terms": len(related),
                "title_chars": len(title),
                "meta_chars": len(meta),
                "questions_to_answer": questions,
            },
        )


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class RevenueEngine:
    """Routes work to the Growth Lead, Solutions Engineer or SEO Team."""

    ROUTES = (
        (
            re.compile(
                r"\b(growth|funnel|experiment|channel|budget|campaign|conversion|"
                r"activation|retention|cac|roas)\b",
                re.I,
            ),
            "growth",
        ),
        (
            re.compile(
                r"\b(solutions?|integration|demo|requirements?|rfp|technical|"
                r"implementation|discovery|fit)\b",
                re.I,
            ),
            "solutions",
        ),
        (
            re.compile(
                r"\b(seo|keywords?|serp|rankings?|on-page|onpage|audit|content|"
                r"backlinks?)\b",
                re.I,
            ),
            "seo",
        ),
    )

    def __init__(
        self,
        growth: GrowthLeadAgent | None = None,
        solutions: SolutionsEngineerAgent | None = None,
        seo: SEOAgent | None = None,
    ) -> None:
        self.growth = growth or GrowthLeadAgent()
        self.solutions = solutions or SolutionsEngineerAgent()
        self.seo = seo or SEOAgent()

    def describe(self) -> list[dict[str, str]]:
        return [agent.describe() for agent in (self.growth, self.solutions, self.seo)]

    def run(self, task: str, payload: Mapping[str, Any] | None = None) -> AgentOutput:
        """Route a free-text task to the agent whose remit claims it."""
        for pattern, attr in self.ROUTES:
            if pattern.search(task):
                return getattr(self, attr).run(task, payload)
        raise ValueError(
            f"No agent claims task {task!r}. Mention growth/funnel/experiment, "
            "integration/demo, or SEO/keyword/content."
        )

    def plan(self, payload: Mapping[str, Any] | None = None) -> dict[str, AgentOutput]:
        """Run the sections present in payload: 'growth', 'solutions', 'seo'."""
        payload = dict(payload or {})
        sections = {
            "growth": self.growth,
            "solutions": self.solutions,
            "seo": self.seo,
        }
        present = {key: agent for key, agent in sections.items() if key in payload}
        if not present:
            raise ValueError(
                "plan() needs a 'growth', 'solutions' or 'seo' payload section"
            )
        return {
            agent.name: agent.run_all(payload[key])
            for key, agent in present.items()
        }


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _demo_payloads() -> dict[str, dict[str, Any]]:
    """Default demo payloads, shared by the demo and the CSV export."""
    growth_payload = {
        "experiments": [
            {"name": "Onboarding checklist", "impact": 8, "confidence": 7, "ease": 9},
            {"name": "Pricing page A/B test", "impact": 9, "confidence": 6, "ease": 6},
            {"name": "Lifecycle email nudge", "impact": 6, "confidence": 8, "ease": 8},
            {"name": "Referral incentive", "impact": 7, "confidence": 4, "ease": 5},
        ],
        "funnel": {
            "Visits": 42000,
            "Signups": 3150,
            "Activated": 1260,
            "Trials": 630,
            "Paid": 126,
        },
        "channels": [
            {"name": "Paid search", "spend": 18000, "customers": 54, "revenue": 97200},
            {"name": "Content/SEO", "spend": 6000, "customers": 61, "revenue": 134200},
            {"name": "Outbound", "spend": 14000, "customers": 22, "revenue": 46200},
        ],
    }
    solutions_payload = {
        "requirements": [
            {"name": "SSO (SAML)", "priority": "must"},
            {"name": "Audit logs", "priority": "must"},
            {"name": "REST API", "priority": "should"},
            {"name": "Data residency in EU", "priority": "must"},
            {"name": "Slack notifications", "priority": "could"},
        ],
        "capabilities": [
            "SAML SSO",
            "Audit logs",
            "REST API + webhooks",
            "EU data residency",
        ],
        "integrations": [
            {"name": "Salesforce", "effort": "L", "priority": "must"},
            {"name": "Snowflake export", "effort": "M", "priority": "must"},
            {"name": "HubSpot", "effort": "M", "priority": "should"},
            {"name": "Slack", "effort": "S", "priority": "could"},
        ],
        "persona": "RevOps manager",
        "value_points": ["pipeline dashboard", "automated handoffs", "forecast roll-up"],
        "duration_minutes": 45,
    }
    seo_payload = {
        "keywords": [
            {
                "term": "revenue operations platform",
                "monthly_volume": 2400,
                "difficulty": 42,
                "intent": "commercial",
            },
            {
                "term": "what is revenue operations",
                "monthly_volume": 6600,
                "difficulty": 24,
                "intent": "informational",
            },
            {
                "term": "buy revops software",
                "monthly_volume": 320,
                "difficulty": 18,
                "intent": "transactional",
            },
            {
                "term": "revops tools",
                "monthly_volume": 1900,
                "difficulty": 61,
                "intent": "commercial",
                "current_rank": 14,
            },
        ],
        "page": {
            "title": "Revenue Operations Platform for Growing Teams",
            "meta_description": (
                "See how our revenue operations platform unifies pipeline, "
                "forecasting and handoffs for growing sales teams."
            ),
            "h1": ["Revenue Operations Platform"],
            "word_count": 410,
            "internal_links": 2,
            "images": [
                {"src": "hero.png", "alt": ""},
                {"src": "chart.png", "alt": "Pipeline by stage"},
            ],
            "https": True,
            "mobile_ready": True,
        },
        "keyword": "revops reporting",
        "difficulty": 35,
        "related_terms": ["forecast accuracy", "pipeline coverage"],
    }
    return {
        "growth": growth_payload,
        "solutions": solutions_payload,
        "seo": seo_payload,
    }


def _demo() -> None:
    engine = RevenueEngine()

    print("CORE-BRAIN revenue engine - agents")
    for info in engine.describe():
        print(f"  {info['name']}: {info['role']} [{info['actions']}]")

    payloads = _demo_payloads()
    growth_payload = payloads["growth"]
    solutions_payload = payloads["solutions"]
    seo_payload = payloads["seo"]

    demos = [
        (engine.growth, "prioritise my experiment backlog", growth_payload),
        (engine.growth, "find the funnel leak", growth_payload),
        (engine.growth, "rebalance channel budget", growth_payload),
        (engine.solutions, "assess requirements fit", solutions_payload),
        (engine.solutions, "plan the integrations", solutions_payload),
        (engine.solutions, "build a demo script", solutions_payload),
        (engine.seo, "score these keywords", seo_payload),
        (engine.seo, "run an on-page audit", seo_payload),
        (engine.seo, "write a content brief", seo_payload),
    ]
    for agent, task, payload in demos:
        print()
        print(agent.run(task, payload).render())

    print()
    print("== RevenueEngine.plan (all three agents) ==")
    combined = engine.plan(
        {
            "growth": growth_payload,
            "solutions": solutions_payload,
            "seo": seo_payload,
        }
    )
    for agent_name, output in combined.items():
        print(f"  {agent_name} [{output.action}]: {output.summary}")


def _write_csv(path: Path, outputs: Sequence[AgentOutput]) -> int:
    """Write one row per recommendation; return the number of rows written."""
    rows: list[dict[str, Any]] = []
    for output in outputs:
        for index, rec in enumerate(output.recommendations, 1):
            row: dict[str, Any] = {
                "agent": output.agent,
                "action": output.action,
                "rank": rec.get("rank", index),
            }
            row.update({k: v for k, v in rec.items() if k not in row})
            rows.append(row)
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_to_csv() -> None:
    """Run the default demo plan and write both CSV exports beside this file.

    Growth Lead and Solutions Engineer rows land in ``revenue_leads.csv``;
    SEO keyword and audit rows land in ``seo_results.csv``.
    """
    payloads = _demo_payloads()
    engine = RevenueEngine()
    plan = engine.plan(payloads)

    base = Path(__file__).resolve().parent
    revenue_rows = _write_csv(
        base / "revenue_leads.csv",
        [plan["Growth Lead"], plan["Solutions Engineer"]],
    )
    seo_rows = _write_csv(
        base / "seo_results.csv",
        [
            engine.seo.run("score these keywords", payloads["seo"]),
            engine.seo.run("run an on-page audit", payloads["seo"]),
        ],
    )
    print(
        f"\nWrote {base / 'revenue_leads.csv'} ({revenue_rows} rows) and "
        f"{base / 'seo_results.csv'} ({seo_rows} rows)"
    )


if __name__ == "__main__":
    _demo()
    export_to_csv()
