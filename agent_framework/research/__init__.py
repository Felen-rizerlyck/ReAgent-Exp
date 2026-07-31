"""Research workflow scaffolding."""

from .base import ResearchWorkflow, ResearchWorkflowError
from .pipeline import run_literature_research
from .planner import ResearchPlanner
from .runtime import ResearchRuntimeConfig, build_source_adapter_registry
from .tools import RESEARCH_SYSTEM_PROMPT, build_research_tool_registry
from .processing import RankedSearchResult, deduplicate_search_results, rank_search_results

__all__ = [
    "RESEARCH_SYSTEM_PROMPT",
    "RankedSearchResult",
    "ResearchPlanner",
    "ResearchRuntimeConfig",
    "ResearchWorkflow",
    "ResearchWorkflowError",
    "deduplicate_search_results",
    "build_research_tool_registry",
    "build_source_adapter_registry",
    "rank_search_results",
    "run_literature_research",
]
