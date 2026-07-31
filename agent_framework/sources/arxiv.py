from __future__ import annotations

from dataclasses import asdict
from typing import Any
import xml.etree.ElementTree as ET

import requests

from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapter, SourceAdapterError


ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivSourceAdapter(SourceAdapter):
    source_name = "arxiv"

    def __init__(
        self,
        *,
        base_url: str = "https://export.arxiv.org/api/query",
        user_agent: str = "AgentResearch/0.1",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout

    def search(self, query: SearchQuery, limit: int = 10) -> list[SearchResult]:
        search_query = query.query_text.strip()
        if not search_query:
            raise SourceAdapterError("arXiv search query is empty")

        params = {
            "search_query": f"all:{search_query}",
            "start": 0,
            "max_results": max(1, min(limit, 50)),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        if query.filters.get("category"):
            params["search_query"] = f"cat:{query.filters['category']}"

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceAdapterError(f"arXiv search failed: {exc}") from exc

        return self._parse_feed(response.text, query)

    def fetch(self, result: SearchResult) -> dict[str, Any]:
        return result.raw_payload

    def health_check(self) -> bool:
        return True

    def _parse_feed(self, xml_text: str, query: SearchQuery) -> list[SearchResult]:
        root = ET.fromstring(xml_text)
        results: list[SearchResult] = []

        for entry in root.findall(f"{ATOM_NS}entry"):
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
            summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
            published = entry.findtext(f"{ATOM_NS}published")
            entry_id = (entry.findtext(f"{ATOM_NS}id") or "").strip()
            authors = [
                (author.findtext(f"{ATOM_NS}name") or "").strip()
                for author in entry.findall(f"{ATOM_NS}author")
            ]
            authors = [author for author in authors if author]

            link = None
            pdf_link = None
            for item in entry.findall(f"{ATOM_NS}link"):
                rel = item.attrib.get("rel")
                href = item.attrib.get("href")
                if rel == "alternate" and href:
                    link = href
                if item.attrib.get("title") == "pdf" and href:
                    pdf_link = href

            arxiv_id = entry_id.rsplit("/", 1)[-1] if entry_id else None
            venue = entry.findtext(f"{ARXIV_NS}journal_ref")
            primary_category = entry.find(f"{ARXIV_NS}primary_category")
            categories = [item.attrib.get("term", "") for item in entry.findall(f"{ATOM_NS}category")]
            categories = [category for category in categories if category]

            results.append(
                SearchResult(
                    source=self.source_name,
                    source_id=arxiv_id or entry_id or title,
                    title=title,
                    authors=authors,
                    published_date=published,
                    venue=venue or (primary_category.attrib.get("term") if primary_category is not None else None),
                    abstract=summary,
                    url=link or pdf_link or entry_id or None,
                    arxiv_id=arxiv_id,
                    query=query.query_text,
                    raw_payload={
                        "entry_id": entry_id,
                        "pdf_url": pdf_link,
                        "primary_category": primary_category.attrib.get("term") if primary_category is not None else None,
                        "categories": categories,
                    },
                )
            )

        return results
