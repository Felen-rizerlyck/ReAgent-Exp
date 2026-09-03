from __future__ import annotations

from typing import Any

from agent_framework.research.registry import SourceAdapterRegistry
from agent_framework.research.pipeline import run_literature_research
from agent_framework.research.papers import summarize_local_papers
from agent_framework.research.downloads import download_available_papers
from agent_framework.research.industry import fetch_industry_pages
from agent_framework.research.opensource import read_github_raw_file, search_github_repositories
from agent_framework.research.runtime import build_source_adapter_registry
from agent_framework.schema.research import SearchQuery
from agent_framework.tools import ToolRegistry, tool


RESEARCH_SYSTEM_PROMPT = """
When the user asks for literature research, follow this workflow:
1. Prefer arXiv first for recent technical papers.
2. Use OpenAlex for broader scholarly coverage and metadata validation.
3. Use SerpApi web or scholar search only for discovery, triangulation, and broader web signals.
4. Use GitHub open-source search when the question concerns implementations, frameworks, tools, repositories, APIs, or benchmarks.
5. Use the high-level `research_literature` tool for broad survey tasks.
6. Do not invent citations or claim a paper or repository exists unless it was retrieved from a tool.
7. Summarize results by evidence, not by intuition alone.
8. If the topic is broad, search iteratively and refine the query.
9. Distinguish preprints from peer-reviewed publications.
10. Include source URLs and note uncertainty when evidence is weak.
11. After `research_literature` returns, synthesize the evidence into a structured answer; do not repeat the same broad search unless the returned evidence is clearly insufficient.
12. Use paper abstracts, repository snapshots, and evidence snippets to explain contributions, methods, findings, and limitations instead of only listing titles.
13. In a continuing conversation, reuse prior tool results, saved paper summaries, repository snapshots, and the bound research directory before searching again. Search again only when the follow-up requires missing, newer, or contradictory evidence.
14. When the user asks about a paper or repository already summarized in the current research directory, answer from that summary and the conversation context first.
15. Use `download_research_papers` only when the user requests local paper acquisition or full-text reading. Its default allowlist is limited to arXiv/OpenAlex metadata and it intentionally skips arbitrary search-result landing pages.
""".strip()


def build_research_tool_registry(
    registry: SourceAdapterRegistry | None = None,
    model: Any | None = None,
) -> ToolRegistry:
    source_registry = registry or build_source_adapter_registry()
    tool_registry = ToolRegistry()

    arxiv = source_registry.create("arxiv")
    openalex = source_registry.create("openalex")
    serpapi_web = source_registry.create("serpapi_web")
    serpapi_scholar = source_registry.create("serpapi_scholar")
    github = source_registry.create("opensource_github")

    @tool("Search arXiv for recent papers and preprints. Returns normalized paper records.")
    def search_arxiv(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="arxiv")
        return [_serialize_search_result(item, "high") for item in arxiv.search(search_query, limit=limit)]

    @tool("Search OpenAlex for scholarly works and metadata. Returns normalized paper records.")
    def search_openalex(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="openalex")
        return [_serialize_search_result(item, "high") for item in openalex.search(search_query, limit=limit)]

    @tool("Search the web through SerpApi Google results, then fetch正文 from allowlisted official pages for industry evidence.")
    def search_web(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="serpapi_web", filters={"engine": "google"})
        discovered = serpapi_web.search(search_query, limit=limit)
        pages, _ = fetch_industry_pages(discovered, max_pages=min(max(limit, 5), 10))
        return [_serialize_search_result(item, "medium") for item in (pages or discovered)]

    @tool("Search scholarly results through SerpApi Google Scholar. Useful for broader literature discovery.")
    def search_scholar(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="serpapi_scholar", filters={"engine": "google_scholar"})
        return [_serialize_search_result(item, "medium") for item in serpapi_scholar.search(search_query, limit=limit)]

    @tool("Search GitHub repositories and read their README, docs, latest release, commit, installation, architecture, API, and benchmark evidence.")
    def search_github(query: str, limit: int = 10) -> list[dict[str, Any]]:
        search_query = SearchQuery(query_text=query, source="opensource_github")
        return [_serialize_search_result(item, "medium") for item in github.search(search_query, limit=limit)]

    @tool("Read an explicitly supplied raw.githubusercontent.com file from GitHub.")
    def read_github_file(raw_url: str) -> str:
        return read_github_raw_file(raw_url)

    @tool(
        "Run a multi-source research pass across scholarly sources, allowlisted official industry pages, and GitHub open-source repositories. Choose one or more sources as appropriate, deduplicate and rank results, and return a structured research package."
    )
    def research_literature(query: str, limit: int = 8, sources_csv: str = "arxiv,openalex,serpapi_scholar,serpapi_web,opensource_github") -> dict[str, Any]:
        package = run_literature_research(
            query=query,
            limit=limit,
            sources_csv=sources_csv,
            output_dir=tool_registry.get_research_output_dir(),
        )
        return _compact_research_package(package)

    @tool(
        "Read every PDF in a research result directory's papers (or paper) folder, summarize each paper, and save summaries plus a manifest there. Existing summaries are reused unless force is true."
    )
    def read_and_summarize_papers(research_dir: str, max_papers: int = 10, force: bool = False) -> dict[str, Any]:
        if model is None:
            raise RuntimeError("The paper reading tool requires a configured chat model.")
        return summarize_local_papers(research_dir, model=model, max_papers=max_papers, force=force)

    @tool(
        "Download PDFs only from explicitly allowed scholarly sources (default arxiv/openalex), with caching, retries, size and PDF validation, and a download manifest. SerpApi and arbitrary landing pages are skipped."
    )
    def download_research_papers(
        research_dir: str,
        max_papers: int = 20,
        allowed_sources: str = "arxiv,openalex",
        force: bool = False,
    ) -> dict[str, Any]:
        return download_available_papers(
            research_dir=research_dir,
            max_papers=max_papers,
            allowed_sources=allowed_sources,
            force=force,
        )

    tool_registry.register(search_arxiv)
    tool_registry.register(search_openalex)
    tool_registry.register(search_web)
    tool_registry.register(search_scholar)
    tool_registry.register(search_github)
    tool_registry.register(read_github_file)
    tool_registry.register(research_literature)
    tool_registry.register(read_and_summarize_papers)
    tool_registry.register(download_research_papers)
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
        "source_type": (result.raw_payload or {}).get("source_type"),
        "document_type": (result.raw_payload or {}).get("document_type"),
        "publisher": (result.raw_payload or {}).get("publisher"),
        "is_vendor_claim": (result.raw_payload or {}).get("is_vendor_claim"),
        "repository": (result.raw_payload or {}).get("repository"),
        "version": (result.raw_payload or {}).get("version"),
        "commit": (result.raw_payload or {}).get("commit"),
        "release": (result.raw_payload or {}).get("release"),
        "install": (result.raw_payload or {}).get("install"),
        "architecture": (result.raw_payload or {}).get("architecture"),
        "api": (result.raw_payload or {}).get("api"),
        "benchmark": (result.raw_payload or {}).get("benchmark"),
    }


def _compact_research_package(package: dict[str, Any]) -> dict[str, Any]:
    """Remove provider-specific raw payloads before sending results back to the model."""
    compact = dict(package)
    compact_results: list[dict[str, Any]] = []

    for ranked in package.get("top_results", []):
        if not isinstance(ranked, dict):
            continue
        item = dict(ranked)
        result = item.get("result")
        if isinstance(result, dict):
            result_copy = dict(result)
            raw_payload = result_copy.pop("raw_payload", None)
            if isinstance(raw_payload, dict):
                if raw_payload.get("pdf_url") and not result_copy.get("pdf_url"):
                    result_copy["pdf_url"] = raw_payload["pdf_url"]
                primary_location = raw_payload.get("primary_location") or {}
                if isinstance(primary_location, dict) and primary_location.get("pdf_url"):
                    result_copy.setdefault("pdf_url", primary_location["pdf_url"])
            item["result"] = result_copy
        compact_results.append(item)

    compact["top_results"] = compact_results
    compact["industry_results"] = _compact_ranked_results(package.get("industry_results", []))
    compact["opensource_results"] = _compact_ranked_results(package.get("opensource_results", []))
    return compact


def _compact_ranked_results(results: Any) -> list[dict[str, Any]]:
    compact_results: list[dict[str, Any]] = []
    if not isinstance(results, list):
        return compact_results
    for ranked in results:
        if not isinstance(ranked, dict):
            continue
        item = dict(ranked)
        result = item.get("result")
        if isinstance(result, dict):
            result_copy = dict(result)
            raw_payload = result_copy.pop("raw_payload", None)
            if isinstance(raw_payload, dict):
                for key in (
                    "source_type",
                    "document_type",
                    "publisher",
                    "is_vendor_claim",
                    "retrieved_at",
                    "content_hash",
                    "snapshot_path",
                    "repository",
                    "version",
                    "commit",
                    "release",
                    "install",
                    "architecture",
                    "api",
                    "benchmark",
                ):
                    if key in raw_payload:
                        result_copy[key] = raw_payload[key]
            item["result"] = result_copy
        compact_results.append(item)
    return compact_results
