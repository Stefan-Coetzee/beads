"""
Tests for learning progress service.
"""

import pytest

from ltt.models import BloomLevel, LearnerModel, SubmissionType, TaskCreate, TaskStatus, TaskType
from ltt.services.learning import attach_objective, get_bloom_distribution, get_progress
from ltt.services.progress_service import update_status
from ltt.services.submission_service import create_submission
from ltt.services.task_service import create_task
from ltt.services.validation_service import validate_submission
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_get_progress_empty_project(async_session):
    """Test progress calculation for empty project."""
    # Create empty project
    project = await create_task(
        async_session, TaskCreate(title="Empty Project", task_type=TaskType.PROJECT)
    )
    learner_id = "test-learner"

    # Get progress
    progress = await get_progress(async_session, learner_id, project.id)

    assert progress.learner_id == learner_id
    assert progress.project_id == project.id
    assert progress.total_tasks == 0
    assert progress.completed_tasks == 0
    assert progress.in_progress_tasks == 0
    assert progress.blocked_tasks == 0
    assert progress.completion_percentage == 0.0
    assert progress.total_objectives == 0
    assert progress.objectives_achieved == 0


@pytest.mark.asyncio
async def test_get_progress_with_tasks(async_session):
    """Test progress calculation with various task statuses."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project with tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    task2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    task3 = await create_task(
        async_session,
        TaskCreate(
            title="Task 3", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    # Update statuses
    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)
    await update_status(async_session, task2.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task3.id, learner_id, TaskStatus.BLOCKED)

    # Get progress
    progress = await get_progress(async_session, learner_id, project.id)

    assert progress.total_tasks == 3
    assert progress.completed_tasks == 1
    assert progress.in_progress_tasks == 1
    assert progress.blocked_tasks == 1
    assert progress.completion_percentage == pytest.approx(33.33, rel=0.1)


@pytest.mark.asyncio
async def test_get_progress_with_objectives(async_session):
    """Test progress calculation with learning objectives."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project with tasks
    project = await create_task(
        async_session,
        TaskCreate(
            title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete all tasks"
        ),
    )
    task1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 1",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )
    task2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )

    # Attach objectives
    await attach_objective(async_session, task1.id, "Learn Python basics", BloomLevel.REMEMBER)
    await attach_objective(async_session, task2.id, "Understand functions", BloomLevel.UNDERSTAND)

    # Complete task1 with passing validation
    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    submission1 = await create_submission(
        async_session, task1.id, learner_id, "My work", SubmissionType.TEXT
    )
    await validate_submission(async_session, submission1.id)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Get progress
    progress = await get_progress(async_session, learner_id, project.id)

    assert progress.total_objectives == 2
    assert progress.objectives_achieved == 1  # Only task1 has passing validation


@pytest.mark.asyncio
async def test_get_bloom_distribution(async_session):
    """Test Bloom level distribution calculation."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project with tasks
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete all"),
    )
    task1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 1",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )
    task2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )
    task3 = await create_task(
        async_session,
        TaskCreate(
            title="Task 3",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit",
        ),
    )

    # Attach objectives at different Bloom levels
    await attach_objective(async_session, task1.id, "Remember facts", BloomLevel.REMEMBER)
    await attach_objective(async_session, task1.id, "Remember more facts", BloomLevel.REMEMBER)
    await attach_objective(async_session, task2.id, "Understand concepts", BloomLevel.UNDERSTAND)
    await attach_objective(async_session, task3.id, "Apply knowledge", BloomLevel.APPLY)

    # Complete task1 with passing validation
    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    submission1 = await create_submission(
        async_session, task1.id, learner_id, "My work", SubmissionType.TEXT
    )
    await validate_submission(async_session, submission1.id)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Get Bloom distribution
    distribution = await get_bloom_distribution(async_session, learner_id, project.id)

    assert BloomLevel.REMEMBER in distribution
    assert distribution[BloomLevel.REMEMBER]["total"] == 2
    assert distribution[BloomLevel.REMEMBER]["achieved"] == 2  # Both from completed task1

    assert BloomLevel.UNDERSTAND in distribution
    assert distribution[BloomLevel.UNDERSTAND]["total"] == 1
    assert distribution[BloomLevel.UNDERSTAND]["achieved"] == 0  # Task2 not completed

    assert BloomLevel.APPLY in distribution
    assert distribution[BloomLevel.APPLY]["total"] == 1
    assert distribution[BloomLevel.APPLY]["achieved"] == 0  # Task3 not completed


@pytest.mark.asyncio
async def test_get_progress_lazy_initialization(async_session):
    """Test that progress works with lazy initialization (no progress records)."""
    # Create project with tasks but don't update any statuses
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Task 2", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    learner_id = "test-learner"

    # Get progress (should default to open status)
    progress = await get_progress(async_session, learner_id, project.id)

    assert progress.total_tasks == 2
    assert progress.completed_tasks == 0
    assert progress.in_progress_tasks == 0
    assert progress.blocked_tasks == 0
    # Tasks without progress records are counted as open (not in any of the above)


@pytest.mark.asyncio
async def test_get_progress_nonexistent_project(async_session):
    """Test that getting progress for nonexistent project fails."""
    learner_id = "test-learner"

    with pytest.raises(ValueError, match="does not exist"):
        await get_progress(async_session, learner_id, "nonexistent-project")


@pytest.mark.asyncio
async def test_bloom_distribution_empty_project(async_session):
    """Test Bloom distribution for project with no objectives."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    learner_id = "test-learner"

    distribution = await get_bloom_distribution(async_session, learner_id, project.id)

    assert distribution == {}  # No objectives, empty distribution
