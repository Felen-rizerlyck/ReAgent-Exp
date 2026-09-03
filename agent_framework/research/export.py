from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class ResearchArtifact:
    """Files written for one completed research pass."""

    output_dir: str
    report_path: str
    report_json_path: str
    references_path: str
    references_json_path: str
    metadata_path: str


class ResearchArtifactWriter:
    """Write a research package into a new, self-contained result directory."""

    def __init__(self, output_root: str | Path = "research_results") -> None:
        path = Path(output_root)
        self.output_root = path if path.is_absolute() else PROJECT_ROOT / path

    def write(
        self,
        research_package: dict[str, Any],
        *,
        topic: str,
        output_dir: str | Path | None = None,
    ) -> ResearchArtifact:
        self.output_root.mkdir(parents=True, exist_ok=True)
        target_dir = Path(output_dir) if output_dir else self._new_output_dir(topic)
        if not target_dir.is_absolute():
            target_dir = PROJECT_ROOT / target_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        report = research_package.get("report") or {}
        top_results = research_package.get("top_results") or []
        existing_results = _read_json_list(target_dir / "references.json")
        merged_results = _merge_ranked_results(existing_results, top_results)
        sources = _reference_records(report, merged_results)

        report_path = target_dir / "report.md"
        report_json_path = target_dir / "report.json"
        references_path = target_dir / "references.md"
        references_json_path = target_dir / "references.json"
        metadata_path = target_dir / "metadata.json"

        report_path.write_text(
            self._render_report(report, {**research_package, "top_results": merged_results}),
            encoding="utf-8",
        )
        report_json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        references_path.write_text(self._render_references(sources), encoding="utf-8")
        references_json_path.write_text(
            json.dumps(merged_results, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        previous_metadata = _read_json_object(metadata_path)
        metadata = {
            "query": research_package.get("query", topic),
            "sources": research_package.get("sources", []),
            "source_notes": _merge_records(
                previous_metadata.get("source_notes", []),
                research_package.get("source_notes", []),
            ),
            "raw_result_count": research_package.get("raw_result_count", 0),
            "deduplicated_count": research_package.get("deduplicated_count", 0),
            "ranked_count": research_package.get("ranked_count", 0),
            "generated_at": datetime.utcnow().isoformat(),
            "downloaded_files": [],
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        return ResearchArtifact(
            output_dir=target_dir.as_posix(),
            report_path=report_path.as_posix(),
            report_json_path=report_json_path.as_posix(),
            references_path=references_path.as_posix(),
            references_json_path=references_json_path.as_posix(),
            metadata_path=metadata_path.as_posix(),
        )

    def _new_output_dir(self, topic: str) -> Path:
        safe_topic = _safe_topic_name(topic)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return self.output_root / f"{safe_topic}__{timestamp}"

    @staticmethod
    def _render_report(report: dict[str, Any], research_package: dict[str, Any]) -> str:
        questions = report.get("research_questions") or ["Literature Research"]
        lines = [
            f"# {questions[0]}",
            "",
            "## Executive Summary",
            "",
            str(report.get("executive_summary") or "No executive summary was generated."),
            "",
            "## Retrieval Overview",
            "",
            f"- Raw results: {research_package.get('raw_result_count', 0)}",
            f"- Unique results: {research_package.get('deduplicated_count', 0)}",
            f"- Ranked results: {research_package.get('ranked_count', 0)}",
            f"- Sources: {', '.join(research_package.get('sources', [])) or 'none'}",
            "",
        ]
        source_notes = research_package.get("source_notes") or []
        failed_sources = [
            f"{note.get('source', 'unknown')}: {note.get('reason', note.get('status', 'unavailable'))}"
            for note in source_notes
            if note.get("status") != "ok"
        ]
        if failed_sources:
            lines.extend(["Source issues:", ""])
            lines.extend(f"- {item}" for item in failed_sources)
            lines.append("")

        lines.extend([
            "## Research Questions",
            "",
        ])
        lines.extend(f"- {question}" for question in report.get("research_questions", []))
        lines.extend(["", "## Key Findings", ""])
        lines.extend(f"- {finding}" for finding in report.get("key_findings", []))

        lines.extend(["", "## Important Papers", ""])
        for index, paper in enumerate(report.get("important_papers", []), start=1):
            lines.extend(
                [
                    f"### {index}. {paper.get('title', 'Untitled')}",
                    "",
                    f"- Source: {paper.get('source', 'unknown')}",
                    f"- Authors: {_format_authors(paper.get('authors'))}",
                    f"- Published: {paper.get('published_date') or 'unknown'}",
                    f"- Confidence: {paper.get('confidence', 'unknown')}",
                ]
            )
            if paper.get("url"):
                lines.append(f"- URL: {paper['url']}")
            if paper.get("doi"):
                lines.append(f"- DOI: {paper['doi']}")
            if paper.get("abstract"):
                lines.extend(["", "Abstract evidence:", "", paper["abstract"]])
            if paper.get("reason"):
                lines.extend(["", f"Ranking note: {paper['reason']}"])
            lines.append("")

        lines.extend(["## Open Problems", ""])
        open_problems = report.get("open_problems", [])
        lines.extend(f"- {item}" for item in open_problems)
        if not open_problems:
            lines.append("No open problems were extracted from the available metadata and abstracts in this pass.")
        lines.extend(["", "## Method Notes", "", str(report.get("method_notes") or "")])
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in report.get("limitations", []))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_references(sources: list[dict[str, Any]]) -> str:
        lines = ["# References", ""]
        if not sources:
            lines.append("No references were retrieved.")
            return "\n".join(lines) + "\n"

        for index, source in enumerate(sources, start=1):
            title = source.get("title") or "Untitled"
            details = [
                _format_authors(source.get("authors")),
                source.get("published_date") or "date unknown",
                source.get("source") or "source unknown",
            ]
            lines.append(f"{index}. **{title}** — {', '.join(details)}")
            if source.get("url"):
                lines.append(f"   URL: {source['url']}")
            if source.get("doi"):
                lines.append(f"   DOI: {source['doi']}")
            if source.get("arxiv_id"):
                lines.append(f"   arXiv: {source['arxiv_id']}")
            lines.append("")
        return "\n".join(lines)


def _safe_topic_name(topic: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", topic.strip())
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return (value or "literature_task")[:80]


def _format_authors(authors: Any) -> str:
    if not authors:
        return "authors unknown"
    if isinstance(authors, list):
        return ", ".join(str(author) for author in authors) or "authors unknown"
    return str(authors)


def _reference_records(
    report: dict[str, Any],
    top_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer complete normalized results while retaining report-only compatibility."""
    records: list[dict[str, Any]] = []
    for ranked in top_results:
        result = ranked.get("result") if isinstance(ranked, dict) else None
        if isinstance(result, dict):
            record = dict(result)
            if ranked.get("confidence"):
                record["confidence"] = ranked["confidence"]
            records.append(record)
        elif isinstance(ranked, dict):
            records.append(dict(ranked))

    if records:
        return records
    return list(report.get("sources") or [])


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _merge_ranked_results(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append sub-query evidence while avoiding duplicate repository/paper records."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*previous, *current]:
        result = item.get("result") if isinstance(item, dict) else None
        if not isinstance(result, dict):
            continue
        key = str(result.get("url") or result.get("source_id") or result.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_records(previous: Any, current: Any) -> list[Any]:
    records: list[Any] = []
    for value in [*(previous if isinstance(previous, list) else []), *(current if isinstance(current, list) else [])]:
        if value not in records:
            records.append(value)
    return records
