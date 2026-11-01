"""Core Brain: a multi-agent engine built on a shared memory bus.

Public surface: SharedMemoryBus (inter-agent state), SEOAgent (keyword/viral
optimization), CEOAgentBrain (ROI-driven directives) and CoreBrainOrchestrator
(single-entry-point pipeline).
"""

from brain_core.memory_bus import SharedMemoryBus
from brain_core.seo_agent import SEOAgent
from brain_core.ceo_agent import CEOAgentBrain
from brain_core.orchestrator import CoreBrainOrchestrator

__all__ = [
    "SharedMemoryBus",
    "SEOAgent",
    "CEOAgentBrain",
    "CoreBrainOrchestrator",
]
