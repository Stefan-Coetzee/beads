"""
Tests for submission and validation services.
"""

import pytest
from ltt.models import (
    LearnerModel,
    SubmissionType,
    TaskCreate,
    TaskStatus,
    TaskType,
    ValidatorType,
)
from ltt.services.progress_service import InvalidStatusTransitionError, update_status
from ltt.services.submission_service import (
    InvalidStateError,
    SubmissionNotFoundError,
    TaskNotFoundError,
    create_submission,
    get_attempt_count,
    get_latest_submission,
    get_submission,
    get_submissions,
)
from ltt.services.task_service import create_task
from ltt.services.validation_service import (
    ValidationNotFoundError,
    can_close_task,
    create_manual_validation,
    get_latest_validation,
    get_validation,
    get_validations,
    validate_submission,
)
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id

# ============================================================================
# Submission Service Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_submission(async_session):
    """Test creating a submission for a task."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create submission
    submission = await create_submission(
        async_session, project.id, learner_id, "My submission content", SubmissionType.TEXT
    )

    assert submission.task_id == project.id
    assert submission.learner_id == learner_id
    assert submission.content == "My submission content"
    assert submission.submission_type == SubmissionType.TEXT
    assert submission.attempt_number == 1


@pytest.mark.asyncio
async def test_create_submission_increments_attempt(async_session):
    """Test that second submission has attempt_number=2."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create first submission
    submission1 = await create_submission(
        async_session, project.id, learner_id, "Attempt 1", SubmissionType.TEXT
    )
    assert submission1.attempt_number == 1

    # Create second submission
    submission2 = await create_submission(
        async_session, project.id, learner_id, "Attempt 2", SubmissionType.TEXT
    )
    assert submission2.attempt_number == 2


@pytest.mark.asyncio
async def test_cannot_submit_to_closed_task(async_session):
    """Test that submitting to closed task raises error."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Close the task
    await update_status(async_session, project.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, project.id, learner_id, TaskStatus.CLOSED)

    # Try to submit to closed task
    with pytest.raises(InvalidStateError, match="already closed"):
        await create_submission(
            async_session, project.id, learner_id, "Late submission", SubmissionType.TEXT
        )


@pytest.mark.asyncio
async def test_submit_to_nonexistent_task(async_session):
    """Test that submitting to non-existent task raises error."""
    learner_id = generate_entity_id(PREFIX_LEARNER)

    with pytest.raises(TaskNotFoundError, match="does not exist"):
        await create_submission(
            async_session, "nonexistent-id", learner_id, "Content", SubmissionType.TEXT
        )


@pytest.mark.asyncio
async def test_get_submission(async_session):
    """Test retrieving a submission by ID."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create submission
    created = await create_submission(
        async_session, project.id, learner_id, "Content", SubmissionType.TEXT
    )

    # Get submission
    retrieved = await get_submission(async_session, created.id)

    assert retrieved.id == created.id
    assert retrieved.content == "Content"


@pytest.mark.asyncio
async def test_get_submission_not_found(async_session):
    """Test that getting non-existent submission raises error."""
    with pytest.raises(SubmissionNotFoundError, match="does not exist"):
        await get_submission(async_session, "nonexistent-id")


@pytest.mark.asyncio
async def test_get_submissions(async_session):
    """Test retrieving submissions for a task."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create multiple submissions
    await create_submission(async_session, project.id, learner_id, "Attempt 1", SubmissionType.TEXT)
    await create_submission(async_session, project.id, learner_id, "Attempt 2", SubmissionType.TEXT)
    await create_submission(async_session, project.id, learner_id, "Attempt 3", SubmissionType.TEXT)

    # Get submissions
    submissions = await get_submissions(async_session, project.id, learner_id)

    assert len(submissions) == 3
    # Most recent first
    assert submissions[0].attempt_number == 3
    assert submissions[1].attempt_number == 2
    assert submissions[2].attempt_number == 1


@pytest.mark.asyncio
async def test_get_latest_submission(async_session):
    """Test retrieving the most recent submission."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create submissions
    await create_submission(async_session, project.id, learner_id, "Attempt 1", SubmissionType.TEXT)
    await create_submission(async_session, project.id, learner_id, "Attempt 2", SubmissionType.TEXT)

    # Get latest
    latest = await get_latest_submission(async_session, project.id, learner_id)

    assert latest is not None
    assert latest.attempt_number == 2
    assert latest.content == "Attempt 2"


@pytest.mark.asyncio
async def test_get_latest_submission_none(async_session):
    """Test that get_latest_submission returns None when no submissions exist."""
    learner_id = generate_entity_id(PREFIX_LEARNER)
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    latest = await get_latest_submission(async_session, project.id, learner_id)
    assert latest is None


@pytest.mark.asyncio
async def test_get_attempt_count(async_session):
    """Test counting attempts for a task."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Initially 0
    count = await get_attempt_count(async_session, project.id, learner_id)
    assert count == 0

    # After submissions
    await create_submission(async_session, project.id, learner_id, "Attempt 1", SubmissionType.TEXT)
    await create_submission(async_session, project.id, learner_id, "Attempt 2", SubmissionType.TEXT)

    count = await get_attempt_count(async_session, project.id, learner_id)
    assert count == 2


# ============================================================================
# Validation Service Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_submission(async_session):
    """Test validating a submission."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create submission
    submission = await create_submission(
        async_session, project.id, learner_id, "Valid content", SubmissionType.TEXT
    )

    # Validate
    validation = await validate_submission(async_session, submission.id)

    assert validation.submission_id == submission.id
    assert validation.task_id == project.id
    assert validation.passed is True
    assert validation.error_message is None


@pytest.mark.asyncio
async def test_empty_submission_fails(async_session):
    """Test that empty content fails validation."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create empty submission
    submission = await create_submission(
        async_session, project.id, learner_id, "   ", SubmissionType.TEXT
    )

    # Validate
    validation = await validate_submission(async_session, submission.id)

    assert validation.passed is False
    assert validation.error_message == "Submission is empty"


@pytest.mark.asyncio
async def test_get_validation(async_session):
    """Test retrieving a validation by ID."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    submission = await create_submission(
        async_session, project.id, learner_id, "Content", SubmissionType.TEXT
    )
    created_validation = await validate_submission(async_session, submission.id)

    # Get validation
    retrieved = await get_validation(async_session, created_validation.id)

    assert retrieved.id == created_validation.id
    assert retrieved.passed is True


@pytest.mark.asyncio
async def test_get_validation_not_found(async_session):
    """Test that getting non-existent validation raises error."""
    with pytest.raises(ValidationNotFoundError, match="does not exist"):
        await get_validation(async_session, "nonexistent-id")


@pytest.mark.asyncio
async def test_get_validations(async_session):
    """Test retrieving all validations for a submission."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    submission = await create_submission(
        async_session, project.id, learner_id, "Content", SubmissionType.TEXT
    )

    # Create multiple validations
    await validate_submission(async_session, submission.id)
    await create_manual_validation(async_session, submission.id, False, "Failed manual review")

    # Get validations
    validations = await get_validations(async_session, submission.id)

    assert len(validations) == 2


@pytest.mark.asyncio
async def test_get_latest_validation(async_session):
    """Test getting the latest validation for a task/learner."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    submission1 = await create_submission(
        async_session, project.id, learner_id, "Attempt 1", SubmissionType.TEXT
    )
    await validate_submission(async_session, submission1.id)

    submission2 = await create_submission(
        async_session, project.id, learner_id, "Attempt 2", SubmissionType.TEXT
    )
    validation2 = await validate_submission(async_session, submission2.id)

    # Get latest
    latest = await get_latest_validation(async_session, project.id, learner_id)

    assert latest is not None
    assert latest.id == validation2.id


@pytest.mark.asyncio
async def test_can_close_task_requires_validation_for_subtask(async_session):
    """Test that subtasks require validation to close."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and subtask
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    subtask = await create_task(
        async_session, TaskCreate(title="Subtask", task_type=TaskType.SUBTASK, parent_id=project.id)
    )

    # Try to close without submission
    can_close, reason = await can_close_task(async_session, subtask.id, learner_id)

    assert can_close is False
    assert "No submission found" in reason


@pytest.mark.asyncio
async def test_can_close_task_allows_task_without_validation(async_session):
    """Test that regular tasks don't require validation."""
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
        async_session, TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Can close without validation
    can_close, reason = await can_close_task(async_session, task.id, learner_id)

    assert can_close is True
    assert reason == ""


@pytest.mark.asyncio
async def test_failed_validation_blocks_close(async_session):
    """Test that can_close_task returns False if latest validation failed."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and subtask
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    subtask = await create_task(
        async_session, TaskCreate(title="Subtask", task_type=TaskType.SUBTASK, parent_id=project.id)
    )

    # Create empty submission (fails validation)
    submission = await create_submission(
        async_session, subtask.id, learner_id, "   ", SubmissionType.TEXT
    )
    await validate_submission(async_session, submission.id)

    # Try to close
    can_close, reason = await can_close_task(async_session, subtask.id, learner_id)

    assert can_close is False
    assert "Validation failed" in reason


@pytest.mark.asyncio
async def test_subtask_can_close_with_passing_validation(async_session):
    """Test that subtasks can close with passing validation."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and subtask
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    subtask = await create_task(
        async_session, TaskCreate(title="Subtask", task_type=TaskType.SUBTASK, parent_id=project.id)
    )

    # Create valid submission
    submission = await create_submission(
        async_session, subtask.id, learner_id, "Valid content", SubmissionType.TEXT
    )
    await validate_submission(async_session, submission.id)

    # Can close
    can_close, reason = await can_close_task(async_session, subtask.id, learner_id)

    assert can_close is True
    assert reason == ""


@pytest.mark.asyncio
async def test_close_task_integrates_with_validation(async_session):
    """Test that close_task checks validation before closing."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and subtask
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    subtask = await create_task(
        async_session, TaskCreate(title="Subtask", task_type=TaskType.SUBTASK, parent_id=project.id)
    )

    # Try to close without submission - should fail
    with pytest.raises(InvalidStatusTransitionError, match="No submission found"):
        await update_status(async_session, subtask.id, learner_id, TaskStatus.IN_PROGRESS)
        await update_status(async_session, subtask.id, learner_id, TaskStatus.CLOSED)


@pytest.mark.asyncio
async def test_create_manual_validation(async_session):
    """Test creating a manual validation."""
    # Create learner and task
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    submission = await create_submission(
        async_session, project.id, learner_id, "Content", SubmissionType.TEXT
    )

    # Create manual validation
    validation = await create_manual_validation(
        async_session, submission.id, False, "Needs more detail", actor="reviewer"
    )

    assert validation.submission_id == submission.id
    assert validation.passed is False
    assert validation.error_message == "Needs more detail"
    assert validation.validator_type == ValidatorType.MANUAL
