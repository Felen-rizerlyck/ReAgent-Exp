from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_framework.research.processing import (
    build_research_report,
    deduplicate_search_results,
    rank_search_results,
    result_to_evidence,
)
from agent_framework.research.export import ResearchArtifactWriter
from agent_framework.research.serialization import dataclass_to_dict
from agent_framework.research.runtime import build_source_adapter_registry
from agent_framework.research.industry import fetch_industry_pages, write_industry_snapshots
from agent_framework.research.opensource import write_opensource_snapshots
from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapterError


DEFAULT_RESEARCH_SOURCES = ("arxiv", "openalex", "serpapi_scholar", "serpapi_web", "opensource_github")
SOURCE_ALIASES = {
    "github": "opensource_github",
    "opensource": "opensource_github",
    "open_source": "opensource_github",
    "web": "serpapi_web",
    "google": "serpapi_web",
    "scholar": "serpapi_scholar",
}


def run_literature_research(
    query: str,
    limit: int = 8,
    sources_csv: str = "arxiv,openalex,serpapi_scholar,serpapi_web,opensource_github",
    output_dir: str | None = None,
) -> dict[str, Any]:
    source_names = [_normalize_source_name(source) for source in sources_csv.split(",") if source.strip()]
    if not source_names:
        source_names = list(DEFAULT_RESEARCH_SOURCES)

    registry = build_source_adapter_registry()
    raw_results: list[SearchResult] = []
    source_notes: list[dict[str, Any]] = []

    for source_name in source_names:
        if source_name not in registry.names():
            source_notes.append(
                {
                    "source": source_name,
                    "status": "skipped",
                    "reason": "source adapter not registered",
                }
            )
            continue

        adapter = registry.create(source_name)
        if not adapter.health_check():
            source_notes.append(
                {
                    "source": source_name,
                    "status": "unavailable",
                    "reason": "health check failed",
                }
            )
            continue

        try:
            results = adapter.search(SearchQuery(query_text=query, source=source_name), limit=limit)
            raw_results.extend(results)
            source_notes.append(
                {
                    "source": source_name,
                    "status": "ok",
                    "result_count": len(results),
                }
            )
        except SourceAdapterError as exc:
            source_notes.append(
                {
                    "source": source_name,
                    "status": "error",
                    "reason": str(exc),
                }
            )

    industry_candidates = [item for item in raw_results if item.source == "serpapi_web"]
    industry_results, industry_notes = fetch_industry_pages(
        industry_candidates,
        max_pages=min(max(limit, 5), 10),
    )
    fetched_industry_urls = {item.url for item in industry_results if item.url}
    # Replace the original search snippets with their enriched page records.
    # Otherwise deduplication keeps the earlier serpapi_web record and drops
    # the full industry_web content and snapshot metadata.
    raw_results = [
        item
        for item in raw_results
        if not (item.source == "serpapi_web" and item.url in fetched_industry_urls)
    ]
    raw_results.extend(industry_results)
    if industry_candidates:
        source_notes.append(
            {
                "source": "industry_web",
                "status": "ok" if industry_results else "no_pages",
                "candidate_count": len(industry_candidates),
                "page_count": len(industry_results),
                "page_notes": industry_notes,
            }
        )

    deduplicated_results = deduplicate_search_results(raw_results)
    ranked_results = rank_search_results(query, deduplicated_results)
    evidence_items = [result_to_evidence(query, ranked) for ranked in ranked_results[: min(limit, len(ranked_results))]]
    ranked_industry = [item for item in ranked_results if item.result.source == "industry_web"][: min(limit, len(industry_results))]
    ranked_opensource = [item for item in ranked_results if item.result.source == "opensource_github"][:limit]
    report = build_research_report(
        task_id=_task_id_from_query(query),
        query=query,
        ranked_results=ranked_results,
        evidence_items=evidence_items,
        notes={"source_notes": source_notes},
    )

    research_package = {
        "query": query,
        "sources": source_names,
        "source_notes": source_notes,
        "raw_result_count": len(raw_results),
        "deduplicated_count": len(deduplicated_results),
        "ranked_count": len(ranked_results),
        "evidence_items": [dataclass_to_dict(item) for item in evidence_items],
        "top_results": [dataclass_to_dict(item) for item in ranked_results[: min(limit, len(ranked_results))]],
        "industry_results": [dataclass_to_dict(item) for item in ranked_industry],
        "industry_notes": industry_notes,
        "opensource_results": [dataclass_to_dict(item) for item in ranked_opensource],
        "report": dataclass_to_dict(report),
    }

    try:
        artifact = ResearchArtifactWriter().write(
            research_package,
            topic=query,
            output_dir=output_dir,
        )
        research_package["artifacts"] = dataclass_to_dict(artifact)
        snapshots = write_industry_snapshots(artifact.output_dir, research_package["industry_results"])
        research_package["industry_snapshots"] = snapshots
        Path(artifact.output_dir, "industry_sources.json").write_text(
            json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        opensource_snapshots = write_opensource_snapshots(artifact.output_dir, research_package["opensource_results"])
        research_package["opensource_snapshots"] = opensource_snapshots
        Path(artifact.output_dir, "opensource_sources.json").write_text(
            json.dumps(opensource_snapshots, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        # A local export failure should not discard an otherwise valid search result.
        research_package["artifacts"] = {
            "status": "error",
            "reason": f"Research result export failed: {exc}",
        }

    return research_package


def _normalize_source_name(source: str) -> str:
    value = source.strip().lower().replace("-", "_")
    return SOURCE_ALIASES.get(value, value)


def _task_id_from_query(query: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in query).strip("-")
    normalized = "-".join(part for part in normalized.split("-") if part)
    if not normalized:
        normalized = "literature-task"
    return normalized[:60]
