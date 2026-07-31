from __future__ import annotations

from dataclasses import dataclass, field

from agent_framework.schema.research import ResearchTask


@dataclass(slots=True)
class ResearchPlan:
    """A lightweight plan produced from one research task."""

    task_id: str
    topic: str
    search_steps: list[str] = field(default_factory=list)
    source_preferences: list[str] = field(default_factory=list)
    expected_output: str = "survey"


class ResearchPlanner:
    """Placeholder planner used to shape future research workflows."""

    def build_plan(self, task: ResearchTask) -> ResearchPlan:
        topic = task.topic or task.user_query
        return ResearchPlan(
            task_id=task.task_id,
            topic=topic,
            search_steps=[],
            source_preferences=list(task.source_preferences),
            expected_output=task.output_style,
        )
