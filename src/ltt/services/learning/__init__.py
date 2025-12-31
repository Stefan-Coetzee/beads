"""
Learning services for the Learning Task Tracker.

Learning objectives, progress tracking, summarization, and content management.
"""

from .content import (
    ContentError,
    ContentNotFoundError,
    attach_content_to_task,
    create_content,
    get_content,
    get_relevant_content,
    get_task_content,
)
from .objectives import (
    LearningObjectiveNotFoundError,
    TaskNotFoundError,
    attach_objective,
    get_objectives,
    get_objectives_for_hierarchy,
    remove_objective,
)
from .progress import get_bloom_distribution, get_progress
from .summarization import (
    SummarizationError,
    TaskNotClosedError,
    get_latest_summary,
    get_summaries,
    summarize_completed,
)

__all__ = [
    # Objectives
    "attach_objective",
    "get_objectives",
    "get_objectives_for_hierarchy",
    "remove_objective",
    "LearningObjectiveNotFoundError",
    "TaskNotFoundError",
    # Progress
    "get_progress",
    "get_bloom_distribution",
    # Summarization
    "summarize_completed",
    "get_summaries",
    "get_latest_summary",
    "SummarizationError",
    "TaskNotClosedError",
    # Content
    "create_content",
    "get_content",
    "attach_content_to_task",
    "get_task_content",
    "get_relevant_content",
    "ContentError",
    "ContentNotFoundError",
]
