#!/usr/bin/env python3
"""Core Brain CLI: run one full orchestrator cycle and print the outcome.

Examples:
    python3 main.py
    python3 main.py --topic "AI Video Editing Tools"
    python3 main.py --budget critical --sentiment negative --format article
"""

from __future__ import annotations

import argparse
import json

from brain_core import CoreBrainOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Core Brain pipeline (SEOAgent + CEOAgentBrain via "
            "CoreBrainOrchestrator) and print an executive summary plus the "
            "full bus state as JSON."
        ),
    )
    parser.add_argument(
        "--topic",
        help="Explicit topic for the SEO agent (defaults to the top seeded trend, then the built-in default).",
    )
    parser.add_argument(
        "--budget",
        choices=("healthy", "warning", "critical"),
        help="Budget status driving the CEO budget policy (default: healthy).",
    )
    parser.add_argument(
        "--sentiment",
        choices=("positive", "neutral", "negative"),
        help="Audience sentiment driving the content tone (default: positive).",
    )
    parser.add_argument(
        "--format",
        dest="content_format",
        choices=("video", "article", "hybrid"),
        help="Best-performing content format (default: video).",
    )
    return parser


def print_summary(snapshot: dict) -> None:
    """Print the human-readable executive summary from a bus snapshot."""
    seo = snapshot["seo_strategy"]
    directive = snapshot["ceo_directive"]
    line = "=" * 74

    print(line)
    print(" CORE BRAIN - EXECUTIVE SUMMARY")
    print(line)
    print(f" Topic              : {seo['topic']}")
    print(f" Search intent      : {seo['search_intent']}")
    print(f" SEO score          : {seo['seo_score']}/100")
    print(f" Viral hook         : {seo['viral_hook']}")
    print(f" Primary keywords   : {', '.join(seo['primary_keywords'])}")
    print(f" Secondary keywords : {', '.join(seo['secondary_keywords'])}")
    print("-" * 74)
    print(f" Budget status      : {directive['budget_status']}")
    print(f" Budget policy      : {directive['budget_policy']}")
    print(f" Sentiment          : {directive['sentiment']}")
    print(f" Content tone       : {directive['content_tone']}")
    print(f" Format choice      : {directive['format_choice']}")
    print(f" Expected ROI index : {directive['expected_roi_index']}/100")
    print("-" * 74)
    print(" Sub-agent priorities:")
    for agent, priority in directive["sub_agent_priorities"].items():
        print(f"   {agent:<20}: {priority}")
    print("-" * 74)
    senders = [message["sender"] for message in snapshot["messages"]]
    print(f" Agent messages     : {len(senders)} ({' -> '.join(senders)})")
    print(line)


def main() -> int:
    args = build_parser().parse_args()

    # Only seed the analytics the user actually chose; the CEO brain's own
    # defaults (healthy/positive/video) cover everything else.
    analytics: dict = {}
    if args.budget:
        analytics["budget_status"] = args.budget
    if args.sentiment:
        analytics["sentiment"] = args.sentiment
    if args.content_format:
        analytics["best_format"] = args.content_format

    orchestrator = CoreBrainOrchestrator()
    snapshot = orchestrator.run_cycle(topic=args.topic, analytics=analytics)

    print_summary(snapshot)
    print("FULL BUS STATE (JSON):")
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
