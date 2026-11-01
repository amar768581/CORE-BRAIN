from brain_core.memory import SharedMemoryBus
from brain_core.llm_router import ZeroBudgetLLMRouter
from brain_core.ceo_brain import CEOBrain

DIVIDER = "=" * 74


def print_summary(bus, language, directive):
    print(DIVIDER)
    print(f"Core Brain v2 - {directive.get('language', language)} language")
    print(DIVIDER)
    print(f"Topic            : {directive.get('topic', '')}")
    print(f"Search intent    : {directive.get('search_intent', 'informational')}")
    print(f"SEO score        : {directive.get('seo_score', 0)}/100")
    print(f"Primary keywords : {', '.join(directive.get('primary_keywords', []))}")
    print(f"Hook             : {directive.get('viral_hook', '')}")
    print(f"Hashtags         : {', '.join(directive.get('hashtags', []))}")
    print(f"Budget status    : {directive.get('budget_status', 'healthy')}")
    print(f"Budget policy    : {directive.get('budget_policy', '')}")
    print(f"Sentiment        : {directive.get('sentiment', 'positive')}")
    print(f"Content tone     : {directive.get('content_tone', '')}")
    print(f"Format choice    : {directive.get('format_choice', 'VIDEO')}")
    print(f"Expected ROI     : {directive.get('expected_roi_index', 0)}/100")
    print(f"Engine           : {directive.get('llm_engine', 'rule_based')}")
    if "research_niches" in directive:
        viable = directive["research_niches"]
        print(f"Niche viability  : {len(viable)} zero-budget viable")
        for niche in viable[:5]:
            print(f"  - {niche.get('topic', '?')} (score {niche.get('seo_score', 0)})")
    print(f"Agent messages   : {len(bus.get('messages', []))}")
    for entry in bus.get('messages', [])[-4:]:
        print(f"  {entry['timestamp']}  {entry['sender']:<12} {entry['message'][:60]}")
    print(DIVIDER)


def main():
    bus = SharedMemoryBus()
    ceo = CEOBrain(bus=bus)
    directive = ceo.issue_directive(topic="Core Brain v2", language="en")
    print_summary(bus, "en", directive)


if __name__ == "__main__":
    main()
