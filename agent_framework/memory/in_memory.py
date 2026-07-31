from __future__ import annotations

from dataclasses import replace
from typing import Iterable
from uuid import uuid4

from agent_framework.memory.base import MemoryStore, MemoryStoreError
from agent_framework.schema.research import ResearchSession, ResearchStatus, ResearchTask


class InMemoryResearchMemory(MemoryStore):
    """Simple in-memory store for development and testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, ResearchSession] = {}

    def create_session(self, task: ResearchTask) -> ResearchSession:
        session = ResearchSession(
            session_id=str(uuid4()),
            task=task,
            status=ResearchStatus.DRAFT,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> ResearchSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise MemoryStoreError(f"Session not found: {session_id}") from exc

    def save_session(self, session: ResearchSession) -> None:
        self._sessions[session.session_id] = replace(session)

    def list_sessions(self) -> Iterable[ResearchSession]:
        return self._sessions.values()
