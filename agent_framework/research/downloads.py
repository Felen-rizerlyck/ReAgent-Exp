from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

from agent_framework.research.papers import resolve_research_directory


MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_RETRIES = 3
ALLOWED_HOSTS = {
    "arxiv.org",
    "export.arxiv.org",
    "aclanthology.org",
    "ojs.aaai.org",
}


class PaperDownloadError(Exception):
    """Raised when a paper cannot be downloaded safely."""


def download_available_papers(
    research_dir: str,
    max_papers: int = 20,
    allowed_sources: str = "arxiv,openalex",
    force: bool = False,
    retries: int = DEFAULT_RETRIES,
) -> dict[str, Any]:
    root = resolve_research_directory(research_dir)
    references_path = root / "references.json"
    if not references_path.is_file():
        raise PaperDownloadError(f"references.json not found under {root}")
    try:
        references = json.loads(references_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperDownloadError(f"Could not read references.json: {exc}") from exc

    paper_dir = root / "papers"
    paper_dir.mkdir(parents=True, exist_ok=True)
    allowed = {item.strip().lower() for item in allowed_sources.split(",") if item.strip()}
    records: list[dict[str, Any]] = []
    candidates = _reference_candidates(references)
    for candidate in candidates[: max(1, min(max_papers, 50))]:
        record = _download_candidate(candidate, paper_dir, allowed, force, retries)
        records.append(record)

    manifest = {
        "research_dir": root.as_posix(),
        "papers_dir": paper_dir.as_posix(),
        "generated_at": datetime.utcnow().isoformat(),
        "allowed_sources": sorted(allowed),
        "max_download_bytes": MAX_DOWNLOAD_BYTES,
        "papers": records,
    }
    (root / "paper_download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def _reference_candidates(references: Any) -> list[dict[str, Any]]:
    if not isinstance(references, list):
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ranked in references:
        if not isinstance(ranked, dict):
            continue
        result = ranked.get("result") if isinstance(ranked.get("result"), dict) else ranked
        source = str(result.get("source") or "").lower()
        raw = result.get("raw_payload") if isinstance(result.get("raw_payload"), dict) else {}
        pdf_url = result.get("pdf_url") or raw.get("pdf_url")
        primary = raw.get("primary_location") if isinstance(raw.get("primary_location"), dict) else {}
        pdf_url = pdf_url or primary.get("pdf_url")
        arxiv_id = result.get("arxiv_id")
        if source == "arxiv" and arxiv_id and not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        key = str(result.get("doi") or result.get("arxiv_id") or result.get("url") or result.get("title") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append({
            "source": source,
            "title": result.get("title") or "Untitled paper",
            "source_url": result.get("url"),
            "download_url": pdf_url,
            "arxiv_id": arxiv_id,
            "doi": result.get("doi"),
            "is_oa": primary.get("is_oa") if primary else raw.get("is_oa"),
            "license": primary.get("license") or raw.get("license") or raw.get("best_oa_location", {}).get("license") if isinstance(raw.get("best_oa_location"), dict) else primary.get("license") or raw.get("license"),
        })
    return candidates


def _download_candidate(
    candidate: dict[str, Any],
    paper_dir: Path,
    allowed_sources: set[str],
    force: bool,
    retries: int,
) -> dict[str, Any]:
    source = candidate["source"]
    url = candidate.get("download_url")
    base = {
        "title": candidate["title"],
        "source": source,
        "source_url": candidate.get("source_url"),
        "download_url": url,
        "arxiv_id": candidate.get("arxiv_id"),
        "doi": candidate.get("doi"),
        "is_oa": candidate.get("is_oa"),
        "license": candidate.get("license") or "not provided by metadata",
    }
    if source not in allowed_sources:
        return {**base, "status": "skipped", "reason": "source is not in allowed_sources"}
    if not url:
        return {**base, "status": "skipped", "reason": "no PDF URL in metadata"}
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        return {**base, "status": "skipped", "reason": "PDF host is not explicitly allowlisted"}

    filename = f"{_safe_name(candidate['title'])}.pdf"
    path = paper_dir / filename
    if path.exists() and not force:
        digest = _sha256(path)
        if digest:
            return {**base, "status": "reused", "path": path.as_posix(), "sha256": digest, "bytes": path.stat().st_size}

    last_error = "unknown download error"
    for attempt in range(1, max(1, retries) + 1):
        try:
            response = requests.get(url, stream=True, timeout=(10, 60), headers={"User-Agent": "AgentResearch/0.1"})
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            content_length = int(response.headers.get("Content-Length") or 0)
            if content_length > MAX_DOWNLOAD_BYTES:
                raise PaperDownloadError("declared file size exceeds 50 MB limit")
            temp_path = path.with_suffix(".part")
            total = 0
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise PaperDownloadError("download exceeds 50 MB limit")
                    handle.write(chunk)
            if total < 5 or not _looks_like_pdf(temp_path):
                raise PaperDownloadError(f"response is not a valid PDF (content-type: {content_type or 'unknown'})")
            temp_path.replace(path)
            digest = _sha256(path)
            return {**base, "status": "downloaded", "path": path.as_posix(), "sha256": digest, "bytes": total, "attempts": attempt}
        except (requests.RequestException, OSError, ValueError, PaperDownloadError) as exc:
            last_error = str(exc)
            part = path.with_suffix(".part")
            if part.exists():
                part.unlink()
            if attempt < max(1, retries):
                time.sleep(2 ** (attempt - 1))
    return {**base, "status": "error", "reason": last_error, "attempts": max(1, retries)}


def _looks_like_pdf(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return (value or "paper")[:120]
