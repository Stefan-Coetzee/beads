"""
Summarization service.

Generates hierarchical summaries of completed work for learners.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    BloomLevel,
    LearningObjective,
    StatusSummary,
    StatusSummaryModel,
    TaskModel,
    TaskStatus,
)
from ltt.services.learning.objectives import get_objectives_for_hierarchy
from ltt.services.submission_service import get_submissions
from ltt.services.task_service import get_children
from ltt.utils.ids import PREFIX_SUMMARY, generate_entity_id

# ============================================================================
# Exceptions
# ============================================================================


class SummarizationError(Exception):
    """Base exception for summarization operations."""


class TaskNotClosedError(SummarizationError):
    """Task is not closed for learner."""


# ============================================================================
# Summarization Operations
# ============================================================================


async def summarize_completed(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> StatusSummary:
    """
    Generate a summary for any completed task.

    Works for all task_types:
    - subtask: Summary of the specific work done
    - task: Aggregates subtask summaries + task-level details
    - epic: Aggregates task summaries + epic-level objectives
    - project: Full project summary for portfolio/review

    The summary is stored as a StatusSummary with incremented version.

    Args:
        session: Database session
        task_id: Task to summarize
        learner_id: Learner ID

    Returns:
        StatusSummary with generated summary text

    Raises:
        TaskNotClosedError: If task is not closed for this learner
    """
    # 1. Load task and verify it exists
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        raise ValueError(f"Task {task_id} does not exist")

    # 2. Check if task is closed for this learner
    # Import here to avoid circular dependency
    from ltt.services.progress_service import get_progress

    progress = await get_progress(session, task_id, learner_id)

    if not progress or progress.status != TaskStatus.CLOSED:
        raise TaskNotClosedError(f"Task {task_id} is not closed for learner {learner_id}")

    # 3. Get descendants (if any)
    descendants = await get_children(session, task_id, recursive=True)

    # 4. Get objectives for this task and descendants
    objectives = await get_objectives_for_hierarchy(
        session, task_id, include_ancestors=False, include_descendants=True
    )

    # 5. Get submission history for this learner
    submissions = await get_submissions(session, task_id, learner_id)
    for descendant in descendants:
        descendant_subs = await get_submissions(session, descendant.id, learner_id)
        submissions.extend(descendant_subs)

    # 6. Get child summaries if this is a parent task
    child_summaries = []
    if descendants:
        # Get direct children
        direct_children = [d for d in descendants if d.parent_id == task_id]
        for child in direct_children:
            child_summary = await get_latest_summary(session, child.id, learner_id)
            if child_summary:
                child_summaries.append(child_summary)

    # 7. Build summary data
    summary_data = {
        "task_title": task.title,
        "task_type": task.task_type,
        "task_description": task.description,
        "total_subtasks": len(descendants),
        "total_objectives": len(objectives),
        "total_attempts": sum(s.attempt_number for s in submissions),
        "tasks_with_retries": len([s for s in submissions if s.attempt_number > 1]),
        "objectives_by_level": _group_by_bloom_level(objectives),
        "child_summaries": child_summaries,
    }

    # 8. Generate summary text
    summary_text = _generate_summary_text(summary_data)

    # 9. Store as StatusSummary with incremented version
    latest = await get_latest_summary(session, task_id, learner_id)
    new_version = (latest.version + 1) if latest else 1

    summary_id = generate_entity_id(PREFIX_SUMMARY)
    status_summary = StatusSummaryModel(
        id=summary_id,
        task_id=task_id,
        learner_id=learner_id,
        summary=summary_text,
        version=new_version,
    )
    session.add(status_summary)

    await session.commit()
    await session.refresh(status_summary)

    return StatusSummary.model_validate(status_summary)


async def get_summaries(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> list[StatusSummary]:
    """
    Get all status summaries for a task/learner, ordered by version.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        List of summaries ordered by version (oldest first)
    """
    result = await session.execute(
        select(StatusSummaryModel)
        .where(StatusSummaryModel.task_id == task_id)
        .where(StatusSummaryModel.learner_id == learner_id)
        .order_by(StatusSummaryModel.version)
    )
    summaries = result.scalars().all()

    return [StatusSummary.model_validate(s) for s in summaries]


async def get_latest_summary(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> StatusSummary | None:
    """
    Get the most recent summary for a task/learner.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Latest summary or None if no summaries exist
    """
    result = await session.execute(
        select(StatusSummaryModel)
        .where(StatusSummaryModel.task_id == task_id)
        .where(StatusSummaryModel.learner_id == learner_id)
        .order_by(StatusSummaryModel.version.desc())
        .limit(1)
    )
    summary = result.scalar_one_or_none()

    return StatusSummary.model_validate(summary) if summary else None


# ============================================================================
# Helper Functions
# ============================================================================


def _group_by_bloom_level(objectives: list[LearningObjective]) -> dict[BloomLevel, list[str]]:
    """
    Group objectives by Bloom level.

    Args:
        objectives: List of learning objectives

    Returns:
        Dictionary mapping Bloom levels to objective descriptions
    """
    grouped: dict[BloomLevel, list[str]] = {}

    for obj in objectives:
        if obj.level:
            if obj.level not in grouped:
                grouped[obj.level] = []
            grouped[obj.level].append(obj.description)

    return grouped


def _generate_summary_text(data: dict) -> str:
    """
    Generate summary text from structured data.

    In production, this would use an LLM.
    For MVP, template-based.

    Args:
        data: Summary data dictionary

    Returns:
        Markdown-formatted summary text
    """
    parts = [
        f"## {data['task_title']}",
        "",
    ]

    # Description
    if data.get("task_description"):
        parts.append(data["task_description"])
        parts.append("")

    # Progress summary
    if data["total_subtasks"] > 0:
        parts.append(
            f"Completed {data['total_subtasks']} subtasks with {data['total_objectives']} objectives."
        )
    else:
        parts.append(f"Completed with {data['total_objectives']} objectives.")

    parts.append("")

    # Add objective breakdown by Bloom level
    if data.get("objectives_by_level"):
        parts.append("### Skills Demonstrated")
        for level, objs in data["objectives_by_level"].items():
            parts.append(f"- **{level.value.title()}**: {len(objs)} objectives")
        parts.append("")

    # Note struggles if any
    if data.get("tasks_with_retries", 0) > 0:
        parts.append(f"*Note: {data['tasks_with_retries']} tasks required multiple attempts.*")
        parts.append("")

    return "\n".join(parts)
