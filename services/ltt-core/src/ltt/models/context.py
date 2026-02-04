"""
Task Context for the Learning Task Tracker.

Not stored in DB - computed at runtime for stateless agents.
Session/conversation management is handled by LangGraph.
"""

from dataclasses import dataclass

from .acceptance_criterion import AcceptanceCriterion
from .learner import LearnerProgress
from .learning import LearningObjective
from .status_summary import StatusSummary
from .submission import Submission
from .task import Task, TaskSummary
from .validation import Validation


@dataclass
class TaskContext:
    """
    Complete context loaded for a stateless agent.
    Computed from database, not persisted.

    Note: Session and conversation history are managed by LangGraph,
    not by this system.
    """

    # Current position
    current_task: Task
    task_ancestors: list[Task]  # [parent, grandparent, ..., project]

    # Task details
    learning_objectives: list[LearningObjective]
    acceptance_criteria: list[AcceptanceCriterion]
    task_content: str | None

    # History for this learner
    submissions: list[Submission]
    latest_validation: Validation | None
    status_summaries: list[StatusSummary]

    # Navigation
    ready_tasks: list[TaskSummary]  # in_progress first, then open
    blocked_by: list[TaskSummary]  # What's blocking current task
    children: list[TaskSummary]  # Child tasks

    # Progress
    project_progress: LearnerProgress
