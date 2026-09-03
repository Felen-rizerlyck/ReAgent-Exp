from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Any

from agent_framework.schema.research import (
    EvidenceItem,
    ResearchReport,
    SearchResult,
    SourceConfidence,
)


@dataclass(slots=True)
class RankedSearchResult:
    """A search result with ranking metadata."""

    result: SearchResult
    confidence: SourceConfidence
    relevance: float
    reason: str


def normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"[\W_]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).strip().lower()


def search_result_key(result: SearchResult) -> str:
    for candidate in (result.doi, result.arxiv_id, result.url, result.source_id):
        normalized = normalize_identifier(candidate)
        if normalized:
            return normalized
    return normalize_title(result.title)


def deduplicate_search_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    seen_titles: set[str] = set()
    deduplicated: list[SearchResult] = []

    for result in results:
        key = search_result_key(result)
        title_key = normalize_title(result.title)
        if key in seen or (title_key and title_key in seen_titles):
            continue
        seen.add(key)
        if title_key:
            seen_titles.add(title_key)
        deduplicated.append(result)

    return deduplicated


def source_confidence_for(result: SearchResult, source_confidence: str | None = None) -> SourceConfidence:
    if source_confidence:
        try:
            return SourceConfidence(source_confidence)
        except ValueError:
            pass

    mapping = {
        "arxiv": SourceConfidence.HIGH,
        "openalex": SourceConfidence.HIGH,
        "serpapi": SourceConfidence.MEDIUM,
        "serpapi_web": SourceConfidence.MEDIUM,
        "serpapi_scholar": SourceConfidence.MEDIUM,
        "industry_web": SourceConfidence.MEDIUM,
        "opensource_github": SourceConfidence.MEDIUM,
    }
    return mapping.get(result.source, SourceConfidence.MEDIUM)


def score_search_result(query: str, result: SearchResult) -> float:
    query_terms = _tokenize(query)
    title_terms = _tokenize(result.title)
    abstract_terms = _tokenize(result.abstract or "")

    if not query_terms:
        return 0.0

    title_overlap = len(query_terms & title_terms)
    abstract_overlap = len(query_terms & abstract_terms)

    score = 0.0
    score += title_overlap * 3.0
    score += abstract_overlap * 1.2
    score += _source_weight(result.source)
    score += _recency_bonus(result.published_date)
    score += _specificity_bonus(result)
    return round(score, 4)


def rank_search_results(
    query: str,
    results: list[SearchResult],
    source_confidence_map: dict[str, str] | None = None,
) -> list[RankedSearchResult]:
    ranked: list[RankedSearchResult] = []
    confidence_map = source_confidence_map or {}

    for result in results:
        confidence = source_confidence_for(result, confidence_map.get(result.source))
        relevance = score_search_result(query, result)
        reason = _explain_ranking(query, result, relevance, confidence)
        ranked.append(
            RankedSearchResult(
                result=result,
                confidence=confidence,
                relevance=relevance,
                reason=reason,
            )
        )

    ranked.sort(key=lambda item: (-item.relevance, -_confidence_rank(item.confidence), item.result.title.lower()))
    return ranked


def result_to_evidence(query: str, ranked: RankedSearchResult) -> EvidenceItem:
    result = ranked.result
    snippet = _extract_snippet(result.abstract or result.title, query)
    citations = [value for value in (result.url, result.doi, result.arxiv_id) if value]
    summary = result.abstract or result.title
    return EvidenceItem(
        evidence_id=_evidence_id(result),
        source=result.source,
        title=result.title,
        summary=summary,
        supporting_snippet=snippet,
        confidence=ranked.confidence,
        relevance=ranked.relevance,
        citations=citations,
        metadata={
            "source_id": result.source_id,
            "published_date": result.published_date,
            "venue": result.venue,
            "authors": result.authors,
            "query": query,
        },
    )


def build_research_report(
    task_id: str,
    query: str,
    ranked_results: list[RankedSearchResult],
    evidence_items: list[EvidenceItem],
    notes: dict[str, Any] | None = None,
) -> ResearchReport:
    top_findings = []
    for item in ranked_results[:5]:
        abstract = _compact_text(item.result.abstract or "", max_length=360)
        detail = f": {abstract}" if abstract else ""
        top_findings.append(
            f"{item.result.title}{detail} "
            f"({item.result.source}, {item.confidence.value}, score={item.relevance:.2f})"
        )
    sources = [
        {
            "source": item.result.source,
            "title": item.result.title,
            "url": item.result.url,
            "doi": item.result.doi,
            "arxiv_id": item.result.arxiv_id,
            "score": item.relevance,
            "confidence": item.confidence.value,
        }
        for item in ranked_results
    ]
    return ResearchReport(
        report_id=f"report-{task_id}",
        task_id=task_id,
        executive_summary=(
            f"The search retrieved {len(ranked_results)} unique results and selected "
            f"{len(evidence_items)} evidence items for preliminary synthesis. "
            "The findings below are based on available metadata and abstracts."
        ),
        research_questions=[query],
        key_findings=top_findings,
        important_papers=[_paper_summary(item) for item in ranked_results[:5]],
        open_problems=[],
        method_notes="Results were deduplicated, ranked by query overlap, source confidence, and recency, then converted into evidence items.",
        limitations=[
            "This report is based on retrieved metadata and abstracts only.",
            "Full-text PDF parsing is not yet enabled in this stage.",
        ],
        sources=sources,
        metadata={
            "evidence_count": len(evidence_items),
            "ranked_count": len(ranked_results),
            "generated_at": datetime.utcnow().isoformat(),
            "notes": notes or {},
        },
    )


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 1}


def _source_weight(source: str) -> float:
    return {
        "arxiv": 2.5,
        "openalex": 2.4,
        "serpapi": 1.1,
        "serpapi_web": 1.1,
        "serpapi_scholar": 1.2,
        "industry_web": 1.4,
        "opensource_github": 1.5,
    }.get(source, 0.5)


def _confidence_rank(confidence: SourceConfidence) -> int:
    return {
        SourceConfidence.HIGH: 3,
        SourceConfidence.MEDIUM: 2,
        SourceConfidence.LOW: 1,
    }[confidence]


def _recency_bonus(published_date: str | None) -> float:
    if not published_date:
        return 0.0

    try:
        year = int(published_date[:4])
    except (TypeError, ValueError):
        return 0.0

    current_year = datetime.utcnow().year
    age = max(current_year - year, 0)
    return max(0.0, 1.5 - (age * 0.2))


def _specificity_bonus(result: SearchResult) -> float:
    score = 0.0
    if result.doi:
        score += 0.8
    if result.arxiv_id:
        score += 0.6
    if result.abstract:
        score += 0.4
    if result.venue:
        score += 0.2
    return score


def _extract_snippet(text: str, query: str, max_length: int = 220) -> str:
    if not text:
        return ""

    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", query.lower())
    if not tokens:
        return text[:max_length].strip()

    lower_text = text.lower()
    positions = [lower_text.find(token) for token in tokens if lower_text.find(token) >= 0]
    if positions:
        start = max(min(positions) - 60, 0)
        end = min(start + max_length, len(text))
        return text[start:end].strip()
    return text[:max_length].strip()


def _evidence_id(result: SearchResult) -> str:
    key = search_result_key(result)
    return f"evidence-{key[:48]}"


def _paper_summary(item: RankedSearchResult) -> dict[str, Any]:
    result = item.result
    return {
        "title": result.title,
        "source": result.source,
        "authors": result.authors,
        "published_date": result.published_date,
        "venue": result.venue,
        "url": result.url,
        "doi": result.doi,
        "arxiv_id": result.arxiv_id,
        "abstract": _compact_text(result.abstract or "", max_length=1000) or None,
        "score": item.relevance,
        "confidence": item.confidence.value,
        "reason": item.reason,
    }


def _explain_ranking(query: str, result: SearchResult, relevance: float, confidence: SourceConfidence) -> str:
    reasons: list[str] = []
    if result.source == "arxiv":
        reasons.append("arXiv prioritized for recent technical work")
    if result.doi:
        reasons.append("DOI present")
    if result.arxiv_id:
        reasons.append("arXiv identifier present")
    if result.abstract:
        reasons.append("abstract available")
    if relevance > 0:
        reasons.append("query overlap detected")
    if not reasons:
        reasons.append("baseline source confidence")
    return f"{confidence.value} confidence; " + "; ".join(reasons)


def _compact_text(text: str, max_length: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."
