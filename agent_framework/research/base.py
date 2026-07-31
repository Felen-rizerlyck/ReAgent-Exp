from __future__ import annotations

from abc import ABC, abstractmethod

from agent_framework.schema.research import ResearchReport, ResearchSession, ResearchTask


class ResearchWorkflowError(Exception):
    """Raised when a research workflow step fails."""


class ResearchWorkflow(ABC):
    """Top-level orchestration contract for literature research."""

    @abstractmethod
    def create_task(self, user_query: str) -> ResearchTask:
        """Turn a raw user query into a structured research task."""

    @abstractmethod
    def run(self, task: ResearchTask) -> ResearchReport:
        """Execute the research workflow and produce a report."""

    @abstractmethod
    def run_session(self, session: ResearchSession) -> ResearchSession:
        """Update an existing session in place."""
