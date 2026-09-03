from __future__ import annotations

from datetime import datetime
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import requests

from agent_framework.schema.research import SearchResult


INDUSTRY_PAGE_LIMIT = 5
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_PAGE_CHARACTERS = 18000
OFFICIAL_DOMAIN_ALLOWLIST = {
    "anthropic.com",
    "ai.google.dev",
    "cloud.google.com",
    "cloud.tencent.com",
    "cloud.tencent.cn",
    "github.com",
    "huggingface.co",
    "microsoft.com",
    "openai.com",
    "platform.openai.com",
    "tencent.com",
}


class IndustryPageError(Exception):
    """Raised when an official industry page cannot be safely fetched."""


class _正文提取器(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self._title = True
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._title = False
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        if self._title:
            self.title_parts.append(value)
        self.text_parts.append(value)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        return "\n\n".join(self.text_parts).strip()


def is_allowed_official_url(url: str, allowed_domains: Iterable[str] | None = None) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    domains = set(allowed_domains or OFFICIAL_DOMAIN_ALLOWLIST)
    host = parsed.hostname.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def fetch_industry_pages(
    search_results: list[SearchResult],
    *,
    max_pages: int = INDUSTRY_PAGE_LIMIT,
    allowed_domains: Iterable[str] | None = None,
    retries: int = 3,
) -> tuple[list[SearchResult], list[dict[str, Any]]]:
    pages: list[SearchResult] = []
    notes: list[dict[str, Any]] = []
    candidates = [item for item in search_results if item.url]
    for result in candidates[: max(1, min(max_pages, 10))]:
        try:
            page = _fetch_page(result, allowed_domains=allowed_domains, retries=retries)
            pages.append(page)
            notes.append({"url": result.url, "status": "ok", "title": page.title})
        except IndustryPageError as exc:
            notes.append({"url": result.url, "status": "skipped", "reason": str(exc)})
    return pages, notes


def _fetch_page(
    result: SearchResult,
    *,
    allowed_domains: Iterable[str] | None,
    retries: int,
) -> SearchResult:
    url = result.url or ""
    if not is_allowed_official_url(url, allowed_domains):
        raise IndustryPageError("URL is not an HTTPS page on the official-domain allowlist")
    last_error = "unknown fetch error"
    for attempt in range(1, max(1, retries) + 1):
        try:
            response = requests.get(
                url,
                timeout=(10, 30),
                headers={"User-Agent": "AgentResearch/0.1"},
                allow_redirects=True,
            )
            response.raise_for_status()
            if not is_allowed_official_url(response.url, allowed_domains):
                raise IndustryPageError("redirected URL is outside the official-domain allowlist")
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "text/" not in content_type:
                raise IndustryPageError(f"page is not HTML/text (content-type: {content_type})")
            if len(response.content) > MAX_PAGE_BYTES:
                raise IndustryPageError("page exceeds 2 MB limit")
            parser = _正文提取器()
            parser.feed(response.content.decode(response.encoding or "utf-8", errors="replace"))
            text = parser.text
            if len(text) < 120:
                raise IndustryPageError("page has too little extractable正文")
            text = text[:MAX_PAGE_CHARACTERS]
            final_url = response.url
            payload = {
                "source_type": "official",
                "document_type": "product_or_documentation_page",
                "publisher": _publisher_for_host(urlparse(final_url).hostname or ""),
                "is_vendor_claim": True,
                "retrieved_at": datetime.utcnow().isoformat(),
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "snapshot_markdown": _snapshot_markdown(parser.title or result.title, final_url, text),
                "fetch_attempts": attempt,
            }
            return SearchResult(
                source="industry_web",
                source_id=final_url,
                title=parser.title or result.title,
                authors=result.authors,
                published_date=result.published_date,
                venue=result.venue,
                abstract=text,
                url=final_url,
                query=result.query,
                raw_payload=payload,
            )
        except (requests.RequestException, UnicodeError, OSError, IndustryPageError) as exc:
            last_error = str(exc)
            if attempt < max(1, retries):
                import time
                time.sleep(2 ** (attempt - 1))
    raise IndustryPageError(last_error)


def _snapshot_markdown(title: str, url: str, text: str) -> str:
    return f"# {title}\n\n- Source URL: {url}\n- Source type: official\n- Vendor claim: true\n- Retrieved at: {datetime.utcnow().isoformat()}\n\n{text}\n"


def _publisher_for_host(host: str) -> str:
    host = host.lower()
    for domain, publisher in {
        "tencent.com": "Tencent",
        "tencent.cn": "Tencent",
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "google.com": "Google",
        "microsoft.com": "Microsoft",
        "github.com": "GitHub / repository owner",
    }.items():
        if host == domain or host.endswith("." + domain):
            return publisher
    return host


def write_industry_snapshots(output_dir: str | Path, ranked_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = Path(output_dir) / "industry_sources"
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for item in ranked_results:
        result = item.get("result") if isinstance(item, dict) else None
        if not isinstance(result, dict):
            continue
        raw = result.get("raw_payload")
        if not isinstance(raw, dict) or not raw.get("snapshot_markdown"):
            continue
        path = root / f"{_safe_name(result.get('title', 'industry_page'))}.md"
        path.write_text(str(raw["snapshot_markdown"]), encoding="utf-8")
        records.append({
            "title": result.get("title"),
            "url": result.get("url"),
            "path": path.as_posix(),
            "publisher": raw.get("publisher"),
            "is_vendor_claim": raw.get("is_vendor_claim", True),
            "content_hash": raw.get("content_hash"),
        })
    return records


def _safe_name(value: Any) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return (value or "industry_page")[:120]
