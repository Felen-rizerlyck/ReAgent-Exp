from __future__ import annotations

from typing import Any

import requests

from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapter, SourceAdapterError


class OpenAlexSourceAdapter(SourceAdapter):
    source_name = "openalex"

    def __init__(
        self,
        *,
        base_url: str = "https://api.openalex.org",
        api_key: str | None = None,
        mailto: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mailto = mailto
        self.timeout = timeout

    def search(self, query: SearchQuery, limit: int = 10) -> list[SearchResult]:
        params: dict[str, Any] = {
            "search": query.query_text,
            "per-page": max(1, min(limit, 200)),
        }

        if query.filters:
            params["filter"] = ",".join(f"{key}:{value}" for key, value in query.filters.items())

        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto

        try:
            response = requests.get(
                f"{self.base_url}/works",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceAdapterError(f"OpenAlex search failed: {exc}") from exc

        payload = response.json()
        results: list[SearchResult] = []
        for item in payload.get("results", []):
            authors = [
                authorship.get("author", {}).get("display_name", "")
                for authorship in item.get("authorships", [])
            ]
            authors = [author for author in authors if author]
            abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
            primary_location = item.get("primary_location") or {}
            source_info = primary_location.get("source") or {}
            doi = item.get("doi")
            openalex_id = item.get("id") or item.get("doi") or item.get("display_name")

            results.append(
                SearchResult(
                    source=self.source_name,
                    source_id=openalex_id,
                    title=item.get("display_name") or "",
                    authors=authors,
                    published_date=item.get("publication_date"),
                    venue=source_info.get("display_name") or item.get("host_venue", {}).get("display_name"),
                    abstract=abstract,
                    url=primary_location.get("landing_page_url") or item.get("id"),
                    doi=doi,
                    query=query.query_text,
                    raw_payload=item,
                )
            )

        return results

    def fetch(self, result: SearchResult) -> dict[str, Any]:
        return result.raw_payload

    def health_check(self) -> bool:
        return True


def _reconstruct_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None

    words: list[str] = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))

    ordered = [word for _, word in sorted(words, key=lambda item: item[0])]
    return " ".join(ordered) if ordered else None
