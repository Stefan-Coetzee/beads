"""
Validation service for the Learning Task Tracker.

Validates submissions against acceptance criteria and gates task closure.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    SubmissionModel,
    TaskModel,
    TaskType,
    Validation,
    ValidationModel,
    ValidatorType,
)
from ltt.services.validators import SimpleValidator
from ltt.utils.ids import PREFIX_VALIDATION, generate_entity_id

# ============================================================================
# Exceptions
# ============================================================================


class ValidationError(Exception):
    """Base exception for validation operations."""


class ValidationNotFoundError(ValidationError):
    """Validation does not exist."""


class SubmissionNotFoundError(ValidationError):
    """Referenced submission does not exist."""


# ============================================================================
# Validation Operations
# ============================================================================


async def validate_submission(
    session: AsyncSession,
    submission_id: str,
    validator_type: ValidatorType = ValidatorType.AUTOMATED,
) -> Validation:
    """
    Validate a submission against task acceptance criteria.

    For MVP, uses SimpleValidator (non-empty check).
    In production, this would dispatch to appropriate validators.

    Args:
        session: Database session
        submission_id: Submission to validate
        validator_type: Who/what is validating

    Returns:
        Validation result

    Raises:
        SubmissionNotFoundError: If submission doesn't exist
    """
    # 1. Load submission and task
    submission_result = await session.execute(
        select(SubmissionModel).where(SubmissionModel.id == submission_id)
    )
    submission = submission_result.scalar_one_or_none()

    if not submission:
        raise SubmissionNotFoundError(f"Submission {submission_id} does not exist")

    task_result = await session.execute(select(TaskModel).where(TaskModel.id == submission.task_id))
    task = task_result.scalar_one_or_none()

    # 2. Run validation using SimpleValidator for MVP
    validator = SimpleValidator()
    passed, error_message = await validator.validate(
        content=submission.content,
        acceptance_criteria=task.acceptance_criteria if task else "",
        submission_type=submission.submission_type,
    )

    # 3. Create validation record
    validation_id = generate_entity_id(PREFIX_VALIDATION)
    validation = ValidationModel(
        id=validation_id,
        submission_id=submission_id,
        task_id=submission.task_id,
        passed=passed,
        error_message=error_message,
        validator_type=validator_type.value,
    )
    session.add(validation)

    await session.commit()
    await session.refresh(validation)

    return Validation.model_validate(validation)


async def get_validation(
    session: AsyncSession,
    validation_id: str,
) -> Validation:
    """
    Get a validation by ID.

    Args:
        session: Database session
        validation_id: Validation ID

    Returns:
        Validation

    Raises:
        ValidationNotFoundError: If validation doesn't exist
    """
    result = await session.execute(select(ValidationModel).where(ValidationModel.id == validation_id))
    validation = result.scalar_one_or_none()

    if not validation:
        raise ValidationNotFoundError(f"Validation {validation_id} does not exist")

    return Validation.model_validate(validation)


async def get_validations(
    session: AsyncSession,
    submission_id: str,
) -> list[Validation]:
    """
    Get all validations for a submission.

    Args:
        session: Database session
        submission_id: Submission ID

    Returns:
        List of validations (most recent first)
    """
    result = await session.execute(
        select(ValidationModel)
        .where(ValidationModel.submission_id == submission_id)
        .order_by(ValidationModel.validated_at.desc())
    )
    validations = result.scalars().all()

    return [Validation.model_validate(val) for val in validations]


async def get_latest_validation(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> Validation | None:
    """
    Get the latest validation for a task/learner.

    Used to determine if task can be closed.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Latest validation or None if no validations exist
    """
    result = await session.execute(
        select(ValidationModel)
        .join(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
        .order_by(ValidationModel.validated_at.desc())
        .limit(1)
    )
    validation = result.scalar_one_or_none()

    return Validation.model_validate(validation) if validation else None


async def can_close_task(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> tuple[bool, str]:
    """
    Check if a task can be closed based on validation.

    Rules:
    - Subtasks: MUST have a passing validation
    - Tasks: Allowed (validation is feedback, not gate)
    - Epics: Allowed (no direct submissions)
    - Projects: Allowed (no direct submissions)

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        (can_close, reason)
        - can_close: True if task can be closed
        - reason: Empty string if can close, error message if cannot
    """
    # Load task
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        return False, f"Task {task_id} does not exist"

    # Non-subtasks can always close (validation is optional)
    if task.task_type != TaskType.SUBTASK.value:
        return True, ""

    # Subtasks require passing validation
    latest_validation = await get_latest_validation(session, task_id, learner_id)

    if latest_validation is None:
        return False, "No submission found. Submit your work before closing."

    if not latest_validation.passed:
        error = latest_validation.error_message or "Validation failed"
        return False, f"Validation failed: {error}"

    return True, ""


async def create_manual_validation(
    session: AsyncSession,
    submission_id: str,
    passed: bool,
    error_message: str | None = None,
    actor: str = "manual",
) -> Validation:
    """
    Create a manual validation (for human review).

    Args:
        session: Database session
        submission_id: Submission to validate
        passed: Whether validation passed
        error_message: Error details if failed
        actor: Who created this validation

    Returns:
        Created validation

    Raises:
        SubmissionNotFoundError: If submission doesn't exist
    """
    # Verify submission exists
    submission_result = await session.execute(
        select(SubmissionModel).where(SubmissionModel.id == submission_id)
    )
    submission = submission_result.scalar_one_or_none()

    if not submission:
        raise SubmissionNotFoundError(f"Submission {submission_id} does not exist")

    # Create validation record
    validation_id = generate_entity_id(PREFIX_VALIDATION)
    validation = ValidationModel(
        id=validation_id,
        submission_id=submission_id,
        task_id=submission.task_id,
        passed=passed,
        error_message=error_message,
        validator_type=ValidatorType.MANUAL.value,
    )
    session.add(validation)

    await session.commit()
    await session.refresh(validation)

    return Validation.model_validate(validation)
