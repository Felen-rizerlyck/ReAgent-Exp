from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agent_framework.schema.research import SearchQuery, SearchResult


class SourceAdapterError(Exception):
    """Raised when a source adapter fails."""


class SourceAdapter(ABC):
    """Common interface for all literature search providers."""

    source_name: str

    @abstractmethod
    def search(self, query: SearchQuery, limit: int = 10) -> list[SearchResult]:
        """Return normalized search results for one query."""

    def fetch(self, result: SearchResult) -> dict[str, Any]:
        """Fetch additional metadata or content for a result."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Return whether the adapter is usable."""
        return True
