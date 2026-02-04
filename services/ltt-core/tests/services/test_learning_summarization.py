"""
Tests for learning summarization service.
"""

import pytest

from ltt.models import BloomLevel, LearnerModel, SubmissionType, TaskCreate, TaskStatus, TaskType
from ltt.services.learning import (
    TaskNotClosedError,
    attach_objective,
    get_latest_summary,
    get_summaries,
    summarize_completed,
)
from ltt.services.progress_service import update_status
from ltt.services.submission_service import create_submission
from ltt.services.task_service import create_task
from ltt.services.validation_service import validate_submission
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_summarize_completed_subtask(async_session):
    """Test summarizing a completed subtask."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create task hierarchy
    project = await create_task(
        async_session,
        TaskCreate(
            title="Project",
            task_type=TaskType.PROJECT,
            description="Learning project",
        ),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    subtask = await create_task(
        async_session,
        TaskCreate(
            title="Subtask",
            task_type=TaskType.SUBTASK,
            description="Learn Python basics",
            parent_id=task.id,
            project_id=project.id,
            acceptance_criteria="Submit code",
        ),
    )

    # Attach objective
    await attach_objective(async_session, subtask.id, "Understand variables", BloomLevel.UNDERSTAND)

    # Complete subtask
    await update_status(async_session, subtask.id, learner_id, TaskStatus.IN_PROGRESS)
    submission = await create_submission(
        async_session, subtask.id, learner_id, "my_code.py", SubmissionType.CODE
    )
    await validate_submission(async_session, submission.id)
    await update_status(async_session, subtask.id, learner_id, TaskStatus.CLOSED)

    # Generate summary
    summary = await summarize_completed(async_session, subtask.id, learner_id)

    assert summary.task_id == subtask.id
    assert summary.learner_id == learner_id
    assert summary.version == 1
    assert "Subtask" in summary.summary
    assert "1 objectives" in summary.summary


@pytest.mark.asyncio
async def test_summarize_task_not_closed(async_session):
    """Test that summarizing unclosed task fails."""
    # Create task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    learner_id = "test-learner"

    # Try to summarize before closing
    with pytest.raises(TaskNotClosedError, match="not closed"):
        await summarize_completed(async_session, task.id, learner_id)


@pytest.mark.asyncio
async def test_summarize_with_multiple_attempts(async_session):
    """Test summary notes multiple attempts."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create subtask
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    subtask = await create_task(
        async_session,
        TaskCreate(
            title="Subtask",
            task_type=TaskType.SUBTASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )

    # Make multiple attempts
    await update_status(async_session, subtask.id, learner_id, TaskStatus.IN_PROGRESS)
    sub1 = await create_submission(
        async_session, subtask.id, learner_id, "attempt 1", SubmissionType.TEXT
    )
    await validate_submission(async_session, sub1.id)
    sub2 = await create_submission(
        async_session, subtask.id, learner_id, "attempt 2", SubmissionType.TEXT
    )
    await validate_submission(async_session, sub2.id)
    await update_status(async_session, subtask.id, learner_id, TaskStatus.CLOSED)

    # Generate summary
    summary = await summarize_completed(async_session, subtask.id, learner_id)

    # Summary should note multiple attempts
    assert "multiple attempts" in summary.summary.lower()


@pytest.mark.asyncio
async def test_summarize_hierarchical_task(async_session):
    """Test summarizing a task with subtasks."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create hierarchy
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Parent Task",
            task_type=TaskType.TASK,
            description="Complex task",
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    subtask1 = await create_task(
        async_session,
        TaskCreate(
            title="Subtask 1",
            task_type=TaskType.SUBTASK,
            parent_id=task.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )
    subtask2 = await create_task(
        async_session,
        TaskCreate(
            title="Subtask 2",
            task_type=TaskType.SUBTASK,
            parent_id=task.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )

    # Attach objectives
    await attach_objective(async_session, task.id, "Main objective", BloomLevel.APPLY)
    await attach_objective(async_session, subtask1.id, "Sub-objective 1", BloomLevel.REMEMBER)
    await attach_objective(async_session, subtask2.id, "Sub-objective 2", BloomLevel.UNDERSTAND)

    # Complete subtasks
    for subtask in [subtask1, subtask2]:
        await update_status(async_session, subtask.id, learner_id, TaskStatus.IN_PROGRESS)
        sub = await create_submission(
            async_session, subtask.id, learner_id, "work", SubmissionType.TEXT
        )
        await validate_submission(async_session, sub.id)
        await update_status(async_session, subtask.id, learner_id, TaskStatus.CLOSED)

    # Complete parent task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # Generate summary
    summary = await summarize_completed(async_session, task.id, learner_id)

    assert summary.task_id == task.id
    assert "2 subtasks" in summary.summary
    assert "3 objectives" in summary.summary  # 1 task + 2 subtasks


@pytest.mark.asyncio
async def test_get_summaries_ordered_by_version(async_session):
    """Test getting summaries in version order."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create and complete a task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Complete task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # Generate multiple summaries
    summary1 = await summarize_completed(async_session, task.id, learner_id)
    await summarize_completed(async_session, task.id, learner_id)
    summary3 = await summarize_completed(async_session, task.id, learner_id)

    # Get all summaries
    summaries = await get_summaries(async_session, task.id, learner_id)

    assert len(summaries) == 3
    assert summaries[0].version == 1
    assert summaries[1].version == 2
    assert summaries[2].version == 3
    assert summaries[0].id == summary1.id
    assert summaries[2].id == summary3.id


@pytest.mark.asyncio
async def test_get_latest_summary(async_session):
    """Test getting the most recent summary."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create and complete task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Complete task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # No summary yet
    latest = await get_latest_summary(async_session, task.id, learner_id)
    assert latest is None

    # Generate summaries
    await summarize_completed(async_session, task.id, learner_id)
    summary2 = await summarize_completed(async_session, task.id, learner_id)

    # Get latest
    latest = await get_latest_summary(async_session, task.id, learner_id)
    assert latest is not None
    assert latest.id == summary2.id
    assert latest.version == 2


@pytest.mark.asyncio
async def test_summarize_includes_bloom_levels(async_session):
    """Test summary includes Bloom level breakdown."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create task with objectives at different levels
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Attach objectives at different Bloom levels
    await attach_objective(async_session, task.id, "Remember", BloomLevel.REMEMBER)
    await attach_objective(async_session, task.id, "Understand", BloomLevel.UNDERSTAND)
    await attach_objective(async_session, task.id, "Apply", BloomLevel.APPLY)

    # Complete task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # Generate summary
    summary = await summarize_completed(async_session, task.id, learner_id)

    # Should include Bloom level breakdown
    assert "Skills Demonstrated" in summary.summary
    assert "Remember" in summary.summary
    assert "Understand" in summary.summary
    assert "Apply" in summary.summary


@pytest.mark.asyncio
async def test_summarize_nonexistent_task(async_session):
    """Test summarizing nonexistent task fails."""
    learner_id = "test-learner"

    with pytest.raises(ValueError, match="does not exist"):
        await summarize_completed(async_session, "nonexistent-task", learner_id)
