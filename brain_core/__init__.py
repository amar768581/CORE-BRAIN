"""Core Brain: a multi-agent engine built on a shared memory bus.

Public surface: SharedMemoryBus (inter-agent state), LLMClient (zero-dependency
Groq/Gemini access with automatic fallback), SEOAgent (keyword/viral
optimization), CEOAgentBrain (ROI-driven directives) and CoreBrainOrchestrator
(single-entry-point pipeline).
"""

from brain_core.memory_bus import SharedMemoryBus
from brain_core.llm_client import LLMClient
from brain_core.seo_agent import SEOAgent
from brain_core.ceo_agent import CEOAgentBrain
from brain_core.orchestrator import CoreBrainOrchestrator

__all__ = [
    "SharedMemoryBus",
    "LLMClient",
    "SEOAgent",
    "CEOAgentBrain",
    "CoreBrainOrchestrator",
]
