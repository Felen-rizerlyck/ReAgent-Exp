from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ResearchStatus(str, Enum):
    """Lifecycle status for a research task."""

    DRAFT = "draft"
    PLANNED = "planned"
    SEARCHING = "searching"
    FETCHING = "fetching"
    SYNTHESIZING = "synthesizing"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


class SourceConfidence(str, Enum):
    """Confidence levels for evidence sources."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(slots=True)
class ResearchTask:
    """A user-facing literature research request."""

    task_id: str
    user_query: str
    topic: str | None = None
    scope: str | None = None
    time_range: str | None = None
    source_preferences: list[str] = field(default_factory=list)
    output_style: str = "survey"
    status: ResearchStatus = ResearchStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchQuery:
    """A single search request against one source."""

    query_text: str
    source: str
    language: str = "en"
    filters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    reason: str = ""


@dataclass(slots=True)
class SearchResult:
    """Raw search output normalized into a common structure."""

    source: str
    source_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    published_date: str | None = None
    venue: str | None = None
    abstract: str | None = None
    url: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    query: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceItem:
    """A ranked evidence unit used for synthesis."""

    evidence_id: str
    source: str
    title: str
    summary: str
    supporting_snippet: str | None = None
    confidence: SourceConfidence = SourceConfidence.MEDIUM
    relevance: float = 0.0
    retrieved_at: datetime = field(default_factory=datetime.utcnow)
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchReport:
    """Final research output produced by the workflow."""

    report_id: str
    task_id: str
    executive_summary: str = ""
    research_questions: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    important_papers: list[dict[str, Any]] = field(default_factory=list)
    open_problems: list[str] = field(default_factory=list)
    method_notes: str = ""
    limitations: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchSession:
    """Mutable state for one literature research run."""

    session_id: str
    task: ResearchTask
    search_queries: list[SearchQuery] = field(default_factory=list)
    search_results: list[SearchResult] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    report: ResearchReport | None = None
    status: ResearchStatus = ResearchStatus.DRAFT
    notes: dict[str, Any] = field(default_factory=dict)
