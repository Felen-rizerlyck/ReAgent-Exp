from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import ChatModel


ModelFactory = Callable[..., ChatModel]


class ModelRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ModelFactory] = {}

    def register(self, name: str, factory: ModelFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs: Any) -> ChatModel:
        if name not in self._factories:
            available = ", ".join(sorted(self._factories))
            raise ValueError(f"Unknown model provider: {name}. Available: {available}")
        return self._factories[name](**kwargs)
