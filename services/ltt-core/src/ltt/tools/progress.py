"""
Progress tools for agent interface.

Tools for tracking progress: start_task, submit.

Implementation Note (ADR-001):
- Status updates go to learner_task_progress table
- Lazy initialization: creates progress record if doesn't exist
- Validation and submission are learner-scoped
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import SubmissionType, TaskStatus
from ltt.services.dependency_service import get_ready_work, is_task_blocked
from ltt.services.progress_service import (
    InvalidStatusTransitionError,
    close_task,
    get_or_create_progress,
    try_auto_close_ancestors,
    update_status,
)
from ltt.services.submission_service import create_submission
from ltt.services.task_service import get_children, get_task
from ltt.services.validation_service import validate_submission
from ltt.tools.schemas import (
    AutoClosedTask,
    StartTaskContextOutput,
    StartTaskInput,
    StartTaskOutput,
    SubmitInput,
    SubmitOutput,
    TaskSummaryOutput,
)


async def start_task(
    input: StartTaskInput, learner_id: str, session: AsyncSession
) -> StartTaskOutput:
    """
    Start working on a task.

    Sets status to in_progress and returns focused context for teaching.
    Returns a simple "already in progress" message if task already started.

    Implementation Note (ADR-001):
    - Status is written to learner_task_progress, not tasks table
    - Creates progress record if it doesn't exist (lazy initialization)
    - Checks blocking against learner's own progress
    """
    from ltt.services.learning.objectives import get_objectives

    # Get task details
    task = await get_task(session, input.task_id)

    # Get or create learner's progress record
    progress = await get_or_create_progress(session, input.task_id, learner_id)

    # Already in progress - still return context so tutor has what they need
    if progress.status == TaskStatus.IN_PROGRESS.value:
        # Get learning objectives with Bloom levels
        objectives = await get_objectives(session, input.task_id)
        objective_dicts = [{"level": obj.level, "description": obj.description} for obj in objectives]

        context = StartTaskContextOutput(
            task_id=task.id,
            title=task.title,
            task_type=task.task_type,
            status=TaskStatus.IN_PROGRESS.value,
            description=task.description or "",
            acceptance_criteria=task.acceptance_criteria or "",
            content=task.content,
            narrative_context=task.narrative_context,
            learning_objectives=objective_dicts,
            tutor_guidance=task.tutor_guidance,
        )

        return StartTaskOutput(
            success=True,
            task_id=input.task_id,
            status=TaskStatus.IN_PROGRESS.value,
            message=f"Task '{task.title}' is already in progress. Continue working on it.",
            context=context,
        )

    # Check if task is closed
    if progress.status == TaskStatus.CLOSED.value:
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            status=TaskStatus.CLOSED.value,
            message="Cannot start a closed task. Use go_back to reopen it first.",
            context=None,
        )

    # Check if task is blocked by dependencies
    is_blocked, blockers = await is_task_blocked(session, input.task_id, learner_id)
    if is_blocked:
        blocker_titles = [b.title for b in blockers[:3]]
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            status=TaskStatus.BLOCKED.value,
            message=f"Task is blocked by {len(blockers)} other task(s): {', '.join(blocker_titles)}",
            context=None,
        )

    # Set to in_progress
    await update_status(session, input.task_id, learner_id, TaskStatus.IN_PROGRESS)

    # Get learning objectives with Bloom levels
    objectives = await get_objectives(session, input.task_id)
    objective_dicts = [{"level": obj.level, "description": obj.description} for obj in objectives]

    # Build focused context
    context = StartTaskContextOutput(
        task_id=task.id,
        title=task.title,
        task_type=task.task_type,
        status=TaskStatus.IN_PROGRESS.value,
        description=task.description or "",
        acceptance_criteria=task.acceptance_criteria or "",
        content=task.content,
        narrative_context=task.narrative_context,
        learning_objectives=objective_dicts,
        tutor_guidance=task.tutor_guidance,
    )

    return StartTaskOutput(
        success=True,
        task_id=input.task_id,
        status=TaskStatus.IN_PROGRESS.value,
        message=f"Started working on '{task.title}'",
        context=context,
    )


async def submit(input: SubmitInput, learner_id: str, session: AsyncSession) -> SubmitOutput:
    """
    Submit work for a task and trigger validation.

    If validation passes, the task is automatically closed.
    See ADR-002 for rationale.

    IMPORTANT: Task must be started (in_progress) before submission.
    Use start_task first.
    """
    # Check task is in_progress - must call start_task first
    progress = await get_or_create_progress(session, input.task_id, learner_id)
    if progress.status != TaskStatus.IN_PROGRESS.value:
        return SubmitOutput(
            success=False,
            submission_id="",
            attempt_number=0,
            validation_passed=None,
            validation_message=None,
            status=progress.status,
            message=f"Cannot submit: task is '{progress.status}', not 'in_progress'. Use start_task first.",
        )

    # Parse submission type (enum values are lowercase)
    try:
        sub_type = SubmissionType(input.submission_type.lower())
    except ValueError:
        return SubmitOutput(
            success=False,
            submission_id="",
            attempt_number=0,
            validation_passed=None,
            validation_message=f"Invalid submission type: {input.submission_type}",
            status=progress.status,
            message=f"Invalid submission type: {input.submission_type}",
        )

    # Create submission
    submission = await create_submission(
        session, input.task_id, learner_id, input.content, sub_type
    )

    # Validate submission
    validation = await validate_submission(session, submission.id)

    # Get current status (refresh after submission)
    current_status = progress.status

    ready_tasks_list = None
    auto_closed_list = None

    if validation.passed:
        # Try to auto-close the task (reuses existing close_task logic)
        try:
            closed_progress = await close_task(
                session, input.task_id, learner_id, "Passed validation"
            )
            current_status = closed_progress.status
            message = "Validation successful, task complete!"

            # Try to auto-close ancestors (parent task, epic, etc.)
            auto_closed_ids = await try_auto_close_ancestors(
                session, input.task_id, learner_id
            )

            if auto_closed_ids:
                # Fetch details for auto-closed tasks
                auto_closed_list = []
                for aid in auto_closed_ids:
                    auto_task = await get_task(session, aid)
                    if auto_task:
                        auto_closed_list.append(
                            AutoClosedTask(
                                id=auto_task.id,
                                title=auto_task.title,
                                task_type=auto_task.task_type,
                            )
                        )

                # Update message to include auto-closed tasks
                closed_names = ", ".join([t.title for t in auto_closed_list])
                message = f"Validation successful, task complete! Also completed: {closed_names}"

            # Get ready tasks so tutor knows what's next (avoid extra get_ready call)
            task = await get_task(session, input.task_id)
            ready_tasks = await get_ready_work(
                session,
                project_id=task.project_id,
                learner_id=learner_id,
                limit=5,
            )
            ready_tasks_list = []
            for ready_task in ready_tasks:
                ready_progress = await get_or_create_progress(session, ready_task.id, learner_id)
                ready_children = await get_children(session, ready_task.id)
                # Include content and summary for epics and tasks (not subtasks)
                include_content = ready_task.task_type in ("epic", "task")
                ready_tasks_list.append(
                    TaskSummaryOutput(
                        id=ready_task.id,
                        title=ready_task.title,
                        status=ready_progress.status,
                        task_type=ready_task.task_type,
                        priority=ready_task.priority,
                        has_children=len(ready_children) > 0,
                        parent_id=ready_task.parent_id,
                        description=ready_task.description if include_content else None,
                        content=ready_task.content if include_content else None,
                        summary=ready_task.summary if include_content else None,
                    )
                )
        except InvalidStatusTransitionError as e:
            # Task can't be closed yet (e.g., has open subtasks)
            # Provide clear feedback about WHY it can't close
            message = f"Validation passed, but task cannot close yet: {e}. Complete subtasks first."
    else:
        message = f"Validation failed: {validation.error_message}"

    return SubmitOutput(
        success=True,
        submission_id=submission.id,
        attempt_number=submission.attempt_number,
        validation_passed=validation.passed,
        validation_message=validation.error_message if not validation.passed else None,
        status=current_status,
        message=message,
        ready_tasks=ready_tasks_list,
        auto_closed=auto_closed_list,
    )
