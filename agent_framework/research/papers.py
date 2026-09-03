from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from agent_framework.models.base import ChatModel, ModelError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_CHUNK_CHARACTERS = 12000


class PaperReadingError(Exception):
    """Raised when local paper discovery, extraction, or summarization fails."""


@dataclass(slots=True)
class ExtractedPaper:
    path: str
    title: str
    page_count: int
    character_count: int
    text: str


def resolve_research_directory(research_dir: str | Path) -> Path:
    candidate = Path(research_dir)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(PROJECT_ROOT / "research_results")
    except ValueError as exc:
        raise PaperReadingError("research_dir must be under research_results.") from exc
    if not candidate.is_dir():
        raise PaperReadingError(f"Research directory not found: {research_dir}")
    return candidate


def discover_paper_files(research_dir: str | Path) -> list[Path]:
    root = resolve_research_directory(research_dir)
    paper_dir = root / "papers"
    if not paper_dir.is_dir():
        paper_dir = root / "paper"
    if not paper_dir.is_dir():
        raise PaperReadingError(f"No papers or paper directory found under {root}.")
    return sorted(
        (path for path in paper_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.lower(),
    )


def extract_pdf(path: Path, max_characters: int = 120000) -> ExtractedPaper:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PaperReadingError(
            "PDF reading requires pypdf; run: pip install -r requirements.txt"
        ) from exc
    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise PaperReadingError(f"Could not read PDF {path.name}: {exc}") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise PaperReadingError(f"No extractable text found in {path.name}; OCR may be required.")
    if len(text) > max_characters:
        text = text[:max_characters] + "\n\n[Text truncated by the local reader.]"
    return ExtractedPaper(path.as_posix(), path.stem, len(reader.pages), len(text), text)


def summarize_local_papers(
    research_dir: str,
    model: ChatModel,
    max_papers: int = 10,
    force: bool = False,
) -> dict[str, Any]:
    root = resolve_research_directory(research_dir)
    files = discover_paper_files(root)[: max(1, min(max_papers, 20))]
    summary_dir = root / "paper_summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for path in files:
        try:
            summary_path = summary_dir / f"{_safe_name(path.stem)}.md"
            if summary_path.exists() and not force:
                existing = summary_path.read_text(encoding="utf-8")
                records.append({
                    "file": path.name,
                    "summary_path": summary_path.as_posix(),
                    "status": "reused",
                    "summary": existing[:8000],
                })
                continue
            paper = extract_pdf(path)
            summary = _summarize_paper(paper, model)
            summary_path.write_text(
                f"# {paper.title}\n\n- Source PDF: `{path.name}`\n- Pages: {paper.page_count}\n- Extracted characters: {paper.character_count}\n\n{summary.strip()}\n",
                encoding="utf-8",
            )
            records.append({
                "file": path.name,
                "summary_path": summary_path.as_posix(),
                "page_count": paper.page_count,
                "character_count": paper.character_count,
                "status": "ok",
                # Keep the tool response bounded while retaining enough context
                # for the next Agent turn to synthesize across papers.
                "summary": summary[:8000],
            })
        except (PaperReadingError, ModelError) as exc:
            records.append({"file": path.name, "status": "error", "reason": str(exc)})
    manifest = {
        "research_dir": root.as_posix(),
        "papers_dir": (root / "papers" if (root / "papers").is_dir() else root / "paper").as_posix(),
        "summary_dir": summary_dir.as_posix(),
        "generated_at": datetime.utcnow().isoformat(),
        "papers": records,
    }
    (root / "paper_reading_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _summarize_paper(paper: ExtractedPaper, model: ChatModel) -> str:
    chunks = [paper.text[index:index + MAX_CHUNK_CHARACTERS] for index in range(0, len(paper.text), MAX_CHUNK_CHARACTERS)]
    notes: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        response = model.complete([
            {"role": "system", "content": "You are a careful literature reader. Summarize only the supplied paper text and mark missing evidence explicitly."},
            {"role": "user", "content": f"Paper: {paper.title}\nChunk {index}/{len(chunks)}\n\n{chunk}\n\nExtract the research problem, method, experiments, findings, limitations, and details useful for comparison with other papers."},
        ])
        notes.append(response.content.strip())
    combined = "\n\n--- CHUNK SUMMARY ---\n\n".join(notes)
    response = model.complete([
        {"role": "system", "content": "Synthesize a faithful paper summary from the supplied notes. Do not invent details or citations."},
        {"role": "user", "content": f"Create a structured summary of {paper.title}. Include research question, contribution, method/architecture, data and evaluation, main results, limitations, and relevance to the surrounding topic. Distinguish reported facts from interpretation.\n\n{combined}"},
    ])
    return response.content


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return (value or "paper")[:100]
