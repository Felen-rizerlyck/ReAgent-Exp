from __future__ import annotations

from dataclasses import dataclass
import os

from agent_framework.research.opensource import GitHubSourceAdapter
from agent_framework.research.registry import SourceAdapterRegistry
from agent_framework.sources.arxiv import ArxivSourceAdapter
from agent_framework.sources.openalex import OpenAlexSourceAdapter
from agent_framework.sources.serpapi import SerpApiSearchAdapter


@dataclass(slots=True)
class ResearchRuntimeConfig:
    """Environment-backed configuration for research adapters."""

    arxiv_user_agent: str = "AgentResearch/0.1"
    openalex_api_key: str | None = None
    openalex_mailto: str | None = None
    serpapi_api_key: str | None = None
    github_token: str | None = None
    request_timeout: int = 30

    @classmethod
    def from_env(cls) -> "ResearchRuntimeConfig":
        return cls(
            arxiv_user_agent=os.getenv("ARXIV_USER_AGENT", "AgentResearch/0.1"),
            openalex_api_key=os.getenv("OPENALEX_API_KEY"),
            openalex_mailto=os.getenv("OPENALEX_MAILTO"),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            request_timeout=int(os.getenv("RESEARCH_TIMEOUT", "30")),
        )


def build_source_adapter_registry(config: ResearchRuntimeConfig | None = None) -> SourceAdapterRegistry:
    config = config or ResearchRuntimeConfig.from_env()
    registry = SourceAdapterRegistry()
    registry.register(
        "arxiv",
        lambda **kwargs: ArxivSourceAdapter(
            user_agent=config.arxiv_user_agent,
            timeout=config.request_timeout,
            **kwargs,
        ),
    )
    registry.register(
        "openalex",
        lambda **kwargs: OpenAlexSourceAdapter(
            api_key=config.openalex_api_key,
            mailto=config.openalex_mailto,
            timeout=config.request_timeout,
            **kwargs,
        ),
    )
    registry.register(
        "serpapi_web",
        lambda **kwargs: SerpApiSearchAdapter(
            api_key=config.serpapi_api_key or "",
            engine="google",
            source_name="serpapi_web",
            timeout=config.request_timeout,
            **kwargs,
        ),
    )
    registry.register(
        "serpapi_scholar",
        lambda **kwargs: SerpApiSearchAdapter(
            api_key=config.serpapi_api_key or "",
            engine="google_scholar",
            source_name="serpapi_scholar",
            timeout=config.request_timeout,
            **kwargs,
        ),
    )
    registry.register(
        "opensource_github",
        lambda **kwargs: GitHubSourceAdapter(
            token=config.github_token,
            timeout=config.request_timeout,
            **kwargs,
        ),
    )
    return registry
