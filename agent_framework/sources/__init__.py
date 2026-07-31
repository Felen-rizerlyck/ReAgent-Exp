"""Source adapters for literature retrieval."""

from .base import SourceAdapter, SourceAdapterError
from .arxiv import ArxivSourceAdapter
from .openalex import OpenAlexSourceAdapter
from .serpapi import SerpApiSearchAdapter

__all__ = [
    "ArxivSourceAdapter",
    "OpenAlexSourceAdapter",
    "SerpApiSearchAdapter",
    "SourceAdapter",
    "SourceAdapterError",
]
