from __future__ import annotations

from typing import Any

from agent_framework.research.processing import (
    build_research_report,
    deduplicate_search_results,
    rank_search_results,
    result_to_evidence,
)
from agent_framework.research.serialization import dataclass_to_dict
from agent_framework.research.runtime import build_source_adapter_registry
from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapterError


DEFAULT_RESEARCH_SOURCES = ("arxiv", "openalex", "serpapi_scholar")


def run_literature_research(
    query: str,
    limit: int = 8,
    sources_csv: str = "arxiv,openalex,serpapi_scholar",
) -> dict[str, Any]:
    source_names = [source.strip() for source in sources_csv.split(",") if source.strip()]
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

    deduplicated_results = deduplicate_search_results(raw_results)
    ranked_results = rank_search_results(query, deduplicated_results)
    evidence_items = [result_to_evidence(query, ranked) for ranked in ranked_results[: min(limit, len(ranked_results))]]
    report = build_research_report(
        task_id=_task_id_from_query(query),
        query=query,
        ranked_results=ranked_results,
        evidence_items=evidence_items,
        notes={"source_notes": source_notes},
    )

    return {
        "query": query,
        "sources": source_names,
        "source_notes": source_notes,
        "raw_result_count": len(raw_results),
        "deduplicated_count": len(deduplicated_results),
        "ranked_count": len(ranked_results),
        "evidence_items": [dataclass_to_dict(item) for item in evidence_items],
        "top_results": [dataclass_to_dict(item) for item in ranked_results[: min(limit, len(ranked_results))]],
        "report": dataclass_to_dict(report),
    }


def _task_id_from_query(query: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in query).strip("-")
    normalized = "-".join(part for part in normalized.split("-") if part)
    if not normalized:
        normalized = "literature-task"
    return normalized[:60]
