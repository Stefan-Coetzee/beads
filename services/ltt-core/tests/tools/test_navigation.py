"""
Tests for navigation tools (get_ready, show_task, get_context).
"""

import pytest

from ltt.models import (
    BloomLevel,
    DependencyType,
    LearnerModel,
    SubmissionType,
    TaskCreate,
    TaskStatus,
    TaskType,
)
from ltt.services.dependency_service import add_dependency
from ltt.services.learning import attach_objective
from ltt.services.progress_service import update_status
from ltt.services.submission_service import create_submission
from ltt.services.task_service import create_task
from ltt.services.validation_service import validate_submission
from ltt.tools.navigation import get_context, get_ready, show_task
from ltt.tools.schemas import GetContextInput, GetReadyInput, ShowTaskInput
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_get_ready_returns_unblocked_tasks(async_session):
    """Test get_ready returns only unblocked tasks."""
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

    # Make task3 depend on task2 (task3 blocked)
    await add_dependency(async_session, task3.id, task2.id, DependencyType.BLOCKS)

    # Close task1
    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Get ready work
    result = await get_ready(
        GetReadyInput(project_id=project.id, task_type="task"), learner_id, async_session
    )

    # Should only return task2 (task1 closed, task3 blocked)
    assert result.total_ready == 1
    assert len(result.tasks) == 1
    assert result.tasks[0].id == task2.id
    assert result.tasks[0].status == "open"


@pytest.mark.asyncio
async def test_get_ready_prioritizes_in_progress(async_session):
    """Test get_ready returns in_progress tasks first."""
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

    # Set task2 to in_progress
    await update_status(async_session, task2.id, learner_id, TaskStatus.IN_PROGRESS)

    # Get ready work
    result = await get_ready(
        GetReadyInput(project_id=project.id, task_type="task", limit=10), learner_id, async_session
    )

    # Should return task2 first (in_progress), then task1 (open)
    assert result.total_ready == 2
    assert result.tasks[0].id == task2.id
    assert result.tasks[0].status == "in_progress"
    assert result.tasks[1].id == task1.id
    assert result.tasks[1].status == "open"


@pytest.mark.asyncio
async def test_show_task_includes_objectives(async_session):
    """Test show_task includes learning objectives."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Learn Python",
            task_type=TaskType.TASK,
            description="Learn basic Python",
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Attach objectives
    await attach_objective(async_session, task.id, "Understand variables", BloomLevel.UNDERSTAND)
    await attach_objective(async_session, task.id, "Apply functions", BloomLevel.APPLY)

    # Show task
    result = await show_task(ShowTaskInput(task_id=task.id), learner_id, async_session)

    assert result.id == task.id
    assert result.title == "Learn Python"
    assert len(result.learning_objectives) == 2
    assert result.learning_objectives[0]["description"] == "Understand variables"
    assert result.learning_objectives[1]["description"] == "Apply functions"


@pytest.mark.asyncio
async def test_show_task_includes_validation_status(async_session):
    """Test show_task includes latest validation status."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session,
        TaskCreate(
            title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete all tasks"
        ),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )

    # Submit work
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    submission = await create_submission(
        async_session, task.id, learner_id, "my work", SubmissionType.TEXT
    )
    validation = await validate_submission(async_session, submission.id)

    # Show task
    result = await show_task(ShowTaskInput(task_id=task.id), learner_id, async_session)

    assert result.submission_count == 1
    assert result.latest_validation_passed == validation.passed


@pytest.mark.asyncio
async def test_get_context_includes_hierarchy(async_session):
    """Test get_context includes task hierarchy."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create hierarchy
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id, project_id=project.id),
    )

    # Get context
    result = await get_context(GetContextInput(task_id=task.id), learner_id, async_session)

    assert result.current_task.id == task.id
    assert result.project_id == project.id
    # Hierarchy should include task, epic, project (reversed)
    assert len(result.hierarchy) == 2  # epic, project (current task not included)
    assert result.hierarchy[0]["id"] == epic.id
    assert result.hierarchy[1]["id"] == project.id


@pytest.mark.asyncio
async def test_get_context_includes_progress(async_session):
    """Test get_context includes project progress."""
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

    # Complete task1
    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Get context for task2
    result = await get_context(GetContextInput(task_id=task2.id), learner_id, async_session)

    assert result.progress is not None
    assert result.progress["total"] == 2
    assert result.progress["completed"] == 1
    assert result.progress["percentage"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_show_task_includes_dependencies(async_session):
    """Test show_task includes blocking and blocked_by tasks."""
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

    # task2 depends on task1 (task2 blocked by task1)
    await add_dependency(async_session, task2.id, task1.id, DependencyType.BLOCKS)
    # task3 depends on task2 (task3 blocked by task2)
    await add_dependency(async_session, task3.id, task2.id, DependencyType.BLOCKS)

    # Show task2
    result = await show_task(ShowTaskInput(task_id=task2.id), learner_id, async_session)

    # task2 is blocked by task1
    assert len(result.blocked_by) == 1
    assert result.blocked_by[0].id == task1.id

    # task2 blocks task3
    assert len(result.blocks) == 1
    assert result.blocks[0].id == task3.id


@pytest.mark.asyncio
async def test_show_task_includes_tutor_guidance(async_session):
    """Test show_task includes tutor_guidance and narrative_context."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project with narrative_context
    project = await create_task(
        async_session,
        TaskCreate(
            title="Water Analysis",
            task_type=TaskType.PROJECT,
            narrative_context="This data impacts real communities in President Naledi's water initiative.",
        ),
    )

    # Create task with tutor_guidance
    task = await create_task(
        async_session,
        TaskCreate(
            title="Filter Data",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            tutor_guidance={
                "teaching_approach": "Start with real-world context",
                "discussion_prompts": ["What does 500 minutes mean?"],
                "common_mistakes": ["Using = instead of LIKE"],
                "hints_to_give": ["Try SHOW TABLES first"],
            },
        ),
    )

    # Show task
    result = await show_task(ShowTaskInput(task_id=task.id), learner_id, async_session)

    # Verify tutor_guidance
    assert result.tutor_guidance is not None
    assert result.tutor_guidance["teaching_approach"] == "Start with real-world context"
    assert "What does 500 minutes mean?" in result.tutor_guidance["discussion_prompts"]

    # narrative_context comes from project
    assert result.narrative_context is None  # This task doesn't have it (project does)
