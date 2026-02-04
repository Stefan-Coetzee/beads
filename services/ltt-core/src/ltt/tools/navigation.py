"""
Navigation tools for agent interface.

Tools for finding and viewing tasks: get_ready, show_task, get_context.

Implementation Note (ADR-001):
- All status queries join with learner_task_progress
- Task status is per-learner, not global
- Comments filtered by learner_id (shared + learner's private)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.services.dependency_service import get_blocking_tasks, get_ready_work
from ltt.services.learning import get_objectives, get_progress, get_summaries
from ltt.services.progress_service import get_or_create_progress
from ltt.services.submission_service import get_submissions
from ltt.services.task_service import get_ancestors, get_children, get_task
from ltt.services.validation_service import get_latest_validation
from ltt.tools.schemas import (
    GetContextInput,
    GetContextOutput,
    GetReadyInput,
    GetReadyOutput,
    ShowTaskInput,
    TaskDetailOutput,
    TaskSummaryOutput,
)


async def get_ready(input: GetReadyInput, learner_id: str, session: AsyncSession) -> GetReadyOutput:
    """
    Get tasks that are unblocked and ready to work on.

    Returns tasks ordered by:
    1. Status (in_progress first, then open)
    2. Priority (P0 first)
    3. Age (oldest first)

    Implementation Note (ADR-001):
    - Queries learner_task_progress to get per-learner status
    - Falls back to 'open' for tasks without progress records (lazy initialization)
    - Checks dependencies against learner's progress, not global task status
    """
    ready_tasks = await get_ready_work(
        session,
        project_id=input.project_id,
        learner_id=learner_id,
        task_type=input.task_type,
        limit=input.limit,
    )

    # Convert to summaries with content and hierarchical summaries
    summaries = []
    for task in ready_tasks:
        # Get learner-specific status
        progress = await get_or_create_progress(session, task.id, learner_id)

        # Get children count
        children = await get_children(session, task.id)
        has_children = len(children) > 0

        # Include content and summary for epics and tasks (not subtasks)
        include_content = task.task_type in ("epic", "task")

        summaries.append(
            TaskSummaryOutput(
                id=task.id,
                title=task.title,
                status=progress.status,
                task_type=task.task_type,
                priority=task.priority,
                has_children=has_children,
                parent_id=task.parent_id,
                description=task.description if include_content else None,
                content=task.content if include_content else None,
                summary=task.summary if include_content else None,
            )
        )

    in_progress_count = sum(1 for t in summaries if t.status == "in_progress")

    return GetReadyOutput(
        tasks=summaries,
        total_ready=len(ready_tasks),
        message=f"Found {len(ready_tasks)} tasks ready ({in_progress_count} in progress).",
    )


async def show_task(
    input: ShowTaskInput, learner_id: str, session: AsyncSession
) -> TaskDetailOutput:
    """
    Show detailed information about a task.

    Includes learning objectives, structured acceptance criteria, and submission history.

    Implementation Note (ADR-001):
    - Task template (title, description, objectives) from tasks table
    - Status comes from learner_task_progress join (per-learner)
    - Submissions, validations, summaries are learner-scoped
    """
    # Get base task
    task = await get_task(session, input.task_id)

    # Get learner-specific status
    progress = await get_or_create_progress(session, input.task_id, learner_id)

    # Get children
    children = await get_children(session, input.task_id)
    children_summaries = []
    for child in children:
        child_progress = await get_or_create_progress(session, child.id, learner_id)
        child_children = await get_children(session, child.id)
        children_summaries.append(
            TaskSummaryOutput(
                id=child.id,
                title=child.title,
                status=child_progress.status,
                task_type=child.task_type,
                priority=child.priority,
                has_children=len(child_children) > 0,
            )
        )

    # Get learning objectives
    objectives = await get_objectives(session, input.task_id)
    objectives_list = [{"level": obj.level, "description": obj.description} for obj in objectives]

    # Get blocking tasks
    blockers = await get_blocking_tasks(session, input.task_id, learner_id)
    blocked_by_summaries = []
    for blocker in blockers:
        blocker_progress = await get_or_create_progress(session, blocker.id, learner_id)
        blocker_children = await get_children(session, blocker.id)
        blocked_by_summaries.append(
            TaskSummaryOutput(
                id=blocker.id,
                title=blocker.title,
                status=blocker_progress.status,
                task_type=blocker.task_type,
                priority=blocker.priority,
                has_children=len(blocker_children) > 0,
            )
        )

    # Get tasks this one blocks (dependents)
    # Query dependencies where this task is the blocker
    from ltt.services.dependency_service import get_dependents

    dependency_records = await get_dependents(session, input.task_id)
    blocks_summaries = []
    for dep in dependency_records:
        # Get the actual task that depends on this one
        dependent_task = await get_task(session, dep.task_id)
        dependent_progress = await get_or_create_progress(session, dependent_task.id, learner_id)
        dependent_children = await get_children(session, dependent_task.id)
        blocks_summaries.append(
            TaskSummaryOutput(
                id=dependent_task.id,
                title=dependent_task.title,
                status=dependent_progress.status,
                task_type=dependent_task.task_type,
                priority=dependent_task.priority,
                has_children=len(dependent_children) > 0,
            )
        )

    # Get submissions and validation
    submissions = await get_submissions(session, input.task_id, learner_id)
    latest_val = await get_latest_validation(session, input.task_id, learner_id)

    # Get status summaries
    summaries = await get_summaries(session, input.task_id, learner_id)
    summaries_list = [
        {"version": s.version, "summary": s.summary, "created_at": s.created_at.isoformat()}
        for s in summaries
    ]

    return TaskDetailOutput(
        id=task.id,
        title=task.title,
        description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        notes=task.notes,
        status=progress.status,
        task_type=task.task_type,
        priority=task.priority,
        parent_id=task.parent_id,
        children=children_summaries,
        learning_objectives=objectives_list,
        content=task.content,
        tutor_guidance=task.tutor_guidance,
        narrative_context=task.narrative_context,
        blocked_by=blocked_by_summaries,
        blocks=blocks_summaries,
        submission_count=len(submissions),
        latest_validation_passed=latest_val.passed if latest_val else None,
        status_summaries=summaries_list,
    )


async def get_context(
    input: GetContextInput, learner_id: str, session: AsyncSession
) -> GetContextOutput:
    """
    Get full context for a task.

    Use this to understand the current state of a task and what needs to be done.
    Note: Session/conversation context is managed by LangGraph.

    Implementation Note (ADR-001):
    - Status comes from learner's progress record
    - Dependencies checked against learner's progress
    """
    # Get base task
    task = await get_task(session, input.task_id)

    # Get learner-specific status
    progress = await get_or_create_progress(session, input.task_id, learner_id)

    # Get children
    children = await get_children(session, input.task_id)
    has_children = len(children) > 0

    # Build hierarchy (ancestors up to project)
    ancestors = await get_ancestors(session, input.task_id)
    hierarchy = [{"id": t.id, "title": t.title, "type": t.task_type} for t in ancestors]

    # Get ready tasks for project
    ready_tasks_data = await get_ready_work(
        session, project_id=task.project_id, learner_id=learner_id, limit=10
    )
    ready_summaries = []
    for ready_task in ready_tasks_data:
        ready_task_progress = await get_or_create_progress(session, ready_task.id, learner_id)
        ready_children = await get_children(session, ready_task.id)
        ready_summaries.append(
            TaskSummaryOutput(
                id=ready_task.id,
                title=ready_task.title,
                status=ready_task_progress.status,
                task_type=ready_task.task_type,
                priority=ready_task.priority,
                has_children=len(ready_children) > 0,
            )
        )

    # Get project progress
    progress_summary = await get_progress(session, learner_id, task.project_id)
    progress_dict = {
        "completed": progress_summary.completed_tasks,
        "total": progress_summary.total_tasks,
        "percentage": progress_summary.completion_percentage,
    }

    # Get learning objectives
    objectives = await get_objectives(session, input.task_id)
    objectives_list = [{"level": obj.level, "description": obj.description} for obj in objectives]

    # Get status summaries
    summaries = await get_summaries(session, input.task_id, learner_id)
    summaries_list = [
        {"version": s.version, "summary": s.summary, "created_at": s.created_at.isoformat()}
        for s in summaries
    ]

    return GetContextOutput(
        learner_id=learner_id,
        current_task=TaskSummaryOutput(
            id=task.id,
            title=task.title,
            status=progress.status,
            task_type=task.task_type,
            priority=task.priority,
            has_children=has_children,
        ),
        project_id=task.project_id,
        hierarchy=hierarchy,
        ready_tasks=ready_summaries,
        progress=progress_dict,
        acceptance_criteria=task.acceptance_criteria,
        learning_objectives=objectives_list,
        status_summaries=summaries_list,
    )
