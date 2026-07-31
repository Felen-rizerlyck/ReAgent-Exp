from __future__ import annotations

from typing import Any

import requests

from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapter, SourceAdapterError


class SerpApiSearchAdapter(SourceAdapter):
    source_name = "serpapi"

    def __init__(
        self,
        *,
        api_key: str,
        engine: str = "google",
        base_url: str = "https://serpapi.com/search.json",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.engine = engine
        self.base_url = base_url
        self.timeout = timeout

    def search(self, query: SearchQuery, limit: int = 10) -> list[SearchResult]:
        if not self.api_key:
            raise SourceAdapterError(
                "SerpApi API key is missing. Set SERPAPI_API_KEY before using web or scholar search."
            )

        params: dict[str, Any] = {
            "engine": query.filters.get("engine", self.engine),
            "q": query.query_text,
            "api_key": self.api_key,
            "num": max(1, min(limit, 20)),
        }
        params.update({key: value for key, value in query.filters.items() if key != "engine"})

        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceAdapterError(f"SerpApi search failed: {exc}") from exc

        payload = response.json()
        organic_results = (
            payload.get("organic_results")
            or payload.get("scholar_results")
            or payload.get("results")
            or []
        )

        results: list[SearchResult] = []
        for index, item in enumerate(organic_results):
            title = item.get("title") or item.get("snippet") or ""
            link = item.get("link") or item.get("url")
            snippet = item.get("snippet") or item.get("description")
            authors = _extract_authors(item)
            published_date = item.get("date")
            source_id = link or f"{self.engine}:{index}"

            results.append(
                SearchResult(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    authors=authors,
                    published_date=published_date,
                    venue=_extract_venue(item),
                    abstract=snippet,
                    url=link,
                    query=query.query_text,
                    raw_payload=item,
                )
            )

        return results

    def fetch(self, result: SearchResult) -> dict[str, Any]:
        return result.raw_payload

    def health_check(self) -> bool:
        return True


def _extract_authors(item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    publication_info = item.get("publication_info") or {}
    summary = publication_info.get("summary")
    if summary:
        authors.append(summary)

    inline_links = item.get("inline_links") or {}
    if isinstance(inline_links, dict):
        cited_by = inline_links.get("cited_by") or {}
        if isinstance(cited_by, dict):
            authors.extend(cited_by.get("authors", []))

    return [author for author in authors if isinstance(author, str) and author]


def _extract_venue(item: dict[str, Any]) -> str | None:
    publication_info = item.get("publication_info") or {}
    if isinstance(publication_info, dict):
        return publication_info.get("summary")
    return None
