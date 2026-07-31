from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from agent_framework.sources.base import SourceAdapter


class SourceAdapterFactory(Protocol):
    def __call__(self, **kwargs) -> SourceAdapter: ...


class SourceAdapterRegistry:
    """Registry for source adapters."""

    def __init__(self) -> None:
        self._factories: dict[str, SourceAdapterFactory] = {}

    def register(self, name: str, factory: SourceAdapterFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs) -> SourceAdapter:
        if name not in self._factories:
            available = ", ".join(sorted(self._factories))
            raise KeyError(f"Unknown source adapter: {name}. Available: {available}")
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)
