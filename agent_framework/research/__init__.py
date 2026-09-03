"""Research workflow scaffolding."""

from .base import ResearchWorkflow, ResearchWorkflowError
from .export import ResearchArtifact, ResearchArtifactWriter
from .pipeline import run_literature_research
from .planner import ResearchPlanner
from .runtime import ResearchRuntimeConfig, build_source_adapter_registry
from .tools import RESEARCH_SYSTEM_PROMPT, build_research_tool_registry
from .processing import RankedSearchResult, deduplicate_search_results, rank_search_results
from .papers import PaperReadingError, discover_paper_files, summarize_local_papers
from .downloads import PaperDownloadError, download_available_papers
from .industry import IndustryPageError, fetch_industry_pages, is_allowed_official_url
from .opensource import GitHubSourceAdapter, OpenSourceError, read_github_raw_file, search_github_repositories

__all__ = [
    "RESEARCH_SYSTEM_PROMPT",
    "RankedSearchResult",
    "ResearchPlanner",
    "ResearchArtifact",
    "ResearchArtifactWriter",
    "ResearchRuntimeConfig",
    "ResearchWorkflow",
    "ResearchWorkflowError",
    "deduplicate_search_results",
    "build_research_tool_registry",
    "build_source_adapter_registry",
    "rank_search_results",
    "run_literature_research",
    "PaperReadingError",
    "discover_paper_files",
    "summarize_local_papers",
    "PaperDownloadError",
    "download_available_papers",
    "IndustryPageError",
    "fetch_industry_pages",
    "is_allowed_official_url",
    "GitHubSourceAdapter",
    "OpenSourceError",
    "read_github_raw_file",
    "search_github_repositories",
]
