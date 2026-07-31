from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from agent_framework.schema.research import ResearchSession, ResearchTask


class MemoryStoreError(Exception):
    """Raised when a memory store operation fails."""


class MemoryStore(ABC):
    """Abstract storage for research tasks and sessions."""

    @abstractmethod
    def create_session(self, task: ResearchTask) -> ResearchSession:
        """Create a new session for a task."""

    @abstractmethod
    def get_session(self, session_id: str) -> ResearchSession:
        """Load a session by its ID."""

    @abstractmethod
    def save_session(self, session: ResearchSession) -> None:
        """Persist a session."""

    @abstractmethod
    def list_sessions(self) -> Iterable[ResearchSession]:
        """List all sessions."""

