from __future__ import annotations

from typing import Any

from agent_framework.research.registry import SourceAdapterRegistry
from agent_framework.research.pipeline import run_literature_research
from agent_framework.research.runtime import build_source_adapter_registry
from agent_framework.schema.research import SearchQuery
from agent_framework.tools import ToolRegistry, tool


RESEARCH_SYSTEM_PROMPT = """
When the user asks for literature research, follow this workflow:
1. Prefer arXiv first for recent technical papers.
2. Use OpenAlex for broader scholarly coverage and metadata validation.
3. Use SerpApi web or scholar search only for discovery, triangulation, and broader web signals.
4. Use the high-level `research_literature` tool for broad survey tasks.
5. Do not invent citations or claim a paper exists unless it was retrieved from a tool.
6. Summarize results by evidence, not by intuition alone.
7. If the topic is broad, search iteratively and refine the query.
8. Distinguish preprints from peer-reviewed publications.
9. Include source URLs and note uncertainty when evidence is weak.
""".strip()


def build_research_tool_registry(
    registry: SourceAdapterRegistry | None = None,
) -> ToolRegistry:
    source_registry = registry or build_source_adapter_registry()
    tool_registry = ToolRegistry()

    arxiv = source_registry.create("arxiv")
    openalex = source_registry.create("openalex")
    serpapi_web = source_registry.create("serpapi_web")
    serpapi_scholar = source_registry.create("serpapi_scholar")

    @tool("Search arXiv for recent papers and preprints. Returns normalized paper records.")
    def search_arxiv(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="arxiv")
        return [_serialize_search_result(item, "high") for item in arxiv.search(search_query, limit=limit)]

    @tool("Search OpenAlex for scholarly works and metadata. Returns normalized paper records.")
    def search_openalex(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="openalex")
        return [_serialize_search_result(item, "high") for item in openalex.search(search_query, limit=limit)]

    @tool("Search the web through SerpApi Google results. Best for discovery and verification.")
    def search_web(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="serpapi_web", filters={"engine": "google"})
        return [_serialize_search_result(item, "medium") for item in serpapi_web.search(search_query, limit=limit)]

    @tool("Search scholarly results through SerpApi Google Scholar. Useful for broader literature discovery.")
    def search_scholar(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="serpapi_scholar", filters={"engine": "google_scholar"})
        return [_serialize_search_result(item, "medium") for item in serpapi_scholar.search(search_query, limit=limit)]

    @tool(
        "Run a multi-source literature research pass, deduplicate and rank results, and return a structured research package."
    )
    def research_literature(query: str, limit: int = 8, sources_csv: str = "arxiv,openalex,serpapi_scholar") -> dict[str, Any]:
        return run_literature_research(query=query, limit=limit, sources_csv=sources_csv)

    tool_registry.register(search_arxiv)
    tool_registry.register(search_openalex)
    tool_registry.register(search_web)
    tool_registry.register(search_scholar)
    tool_registry.register(research_literature)
    return tool_registry


def _serialize_search_result(result: Any, source_confidence: str) -> dict[str, Any]:
    return {
        "source": result.source,
        "source_id": result.source_id,
        "title": result.title,
        "authors": result.authors,
        "published_date": result.published_date,
        "venue": result.venue,
        "abstract": result.abstract,
        "url": result.url,
        "doi": result.doi,
        "arxiv_id": result.arxiv_id,
        "query": result.query,
        "source_confidence": source_confidence,
    }
