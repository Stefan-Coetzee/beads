# Submissions & Validation Module

> Tracking learner submissions and validating against acceptance criteria.

## Overview

This module handles:
- Recording submissions (proof of work)
- Running validation against acceptance criteria
- Tracking attempt history
- Gating task closure on successful validation

### Core Concepts

**Submission**: An atomic piece of evidence that work was attempted. Could be:
- Code snippet
- SQL query
- Jupyter cell output
- Text response
- Result set

**Validation**: Binary pass/fail check against acceptance criteria.
- Subtasks MUST pass validation to close
- Tasks/Epics may receive feedback even when passing

---

## 1. Service Interface

```python
from typing import List, Optional, Tuple
from datetime import datetime
from ltt.models import (
    Submission, SubmissionCreate, SubmissionType,
    Validation, ValidationCreate, ValidatorType,
    Task
)


class SubmissionService:
    """
    Service for managing learner submissions.
    """

    def __init__(self, db_session, event_service: "EventService"):
        self.db = db_session
        self.events = event_service

    # ─────────────────────────────────────────────────────────────
    # Submission Operations
    # ─────────────────────────────────────────────────────────────

    async def create_submission(
        self,
        task_id: str,
        learner_id: str,
        content: str,
        submission_type: SubmissionType,
        session_id: Optional[str] = None,
        auto_validate: bool = True
    ) -> Tuple[Submission, Optional[Validation]]:
        """
        Create a submission for a task.

        Automatically:
        - Calculates attempt number
        - Triggers validation if auto_validate=True
        - Records events

        Args:
            task_id: Task being submitted for
            learner_id: Who is submitting
            content: The submission content
            submission_type: Type of content
            session_id: Optional session context
            auto_validate: Whether to run validation immediately

        Returns:
            (submission, validation) - validation is None if auto_validate=False
        """
        ...

    async def get_submission(
        self,
        submission_id: str
    ) -> Submission:
        """Get a submission by ID."""
        ...

    async def get_submissions(
        self,
        task_id: str,
        learner_id: str,
        limit: int = 10
    ) -> List[Submission]:
        """
        Get submissions for a task by a learner.

        Returns most recent first.
        """
        ...

    async def get_latest_submission(
        self,
        task_id: str,
        learner_id: str
    ) -> Optional[Submission]:
        """Get the most recent submission for a task."""
        ...

    async def get_attempt_count(
        self,
        task_id: str,
        learner_id: str
    ) -> int:
        """Get number of attempts for a task."""
        ...


class ValidationService:
    """
    Service for validating submissions.
    """

    def __init__(self, db_session, event_service: "EventService"):
        self.db = db_session
        self.events = event_service

    # ─────────────────────────────────────────────────────────────
    # Validation Operations
    # ─────────────────────────────────────────────────────────────

    async def validate_submission(
        self,
        submission_id: str,
        validator_type: ValidatorType = ValidatorType.AUTOMATED
    ) -> Validation:
        """
        Validate a submission against task acceptance criteria.

        Args:
            submission_id: Submission to validate
            validator_type: Who/what is validating

        Returns:
            Validation result
        """
        ...

    async def get_validation(
        self,
        validation_id: str
    ) -> Validation:
        """Get a validation by ID."""
        ...

    async def get_validations(
        self,
        submission_id: str
    ) -> List[Validation]:
        """Get all validations for a submission."""
        ...

    async def get_latest_validation(
        self,
        task_id: str,
        learner_id: str
    ) -> Optional[Validation]:
        """
        Get the latest validation for a task/learner.

        Used to determine if task can be closed.
        """
        ...

    async def can_close_task(
        self,
        task_id: str,
        learner_id: str
    ) -> Tuple[bool, str]:
        """
        Check if a task can be closed based on validation.

        For subtasks: requires passing validation.
        For tasks/epics: always allowed (feedback is optional).

        Returns:
            (can_close, reason)
        """
        ...

    async def create_manual_validation(
        self,
        submission_id: str,
        passed: bool,
        error_message: Optional[str] = None,
        actor: str = "manual"
    ) -> Validation:
        """
        Create a manual validation (for human review).
        """
        ...
```

---

## 2. Submission Flow

```
┌─────────────────────┐
│  Learner Submits    │
│  (content + type)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Calculate Attempt  │
│  Number             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Store Submission   │
│  Record Event       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Auto-Validate?     │──────No───────┐
└──────────┬──────────┘               │
           │ Yes                       │
           ▼                           │
┌─────────────────────┐               │
│  Load Task AC       │               │
│  (Acceptance Crit.) │               │
└──────────┬──────────┘               │
           │                           │
           ▼                           │
┌─────────────────────┐               │
│  Run Validation     │               │
│  (Simple check)     │               │
└──────────┬──────────┘               │
           │                           │
     ┌─────┴─────┐                    │
     │           │                     │
   PASS        FAIL                   │
     │           │                     │
     ▼           ▼                     │
┌─────────┐ ┌─────────────────┐       │
│ passed  │ │ passed=False    │       │
│ =True   │ │ error_message   │       │
└─────────┘ └─────────────────┘       │
     │           │                     │
     └─────┬─────┘                    │
           │                           │
           ▼                           │
┌─────────────────────┐               │
│  Store Validation   │◄──────────────┘
│  Record Event       │  (validation=None)
└─────────────────────┘
```

---

## 3. Implementation

### Create Submission

```python
async def create_submission(
    db,
    task_id: str,
    learner_id: str,
    content: str,
    submission_type: SubmissionType,
    session_id: Optional[str] = None,
    auto_validate: bool = True,
    event_service: Optional[EventService] = None
) -> Tuple[Submission, Optional[Validation]]:
    """
    Create a submission with optional auto-validation.
    """
    # 1. Verify task exists and is in valid state
    task = await db.get(TaskModel, task_id)
    if not task:
        raise NotFoundError(task_id)

    if task.status == TaskStatus.CLOSED.value:
        raise InvalidStateError(f"Task '{task_id}' is already closed")

    # 2. Calculate attempt number
    count_result = await db.execute(
        select(func.count())
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
    )
    attempt_number = (count_result.scalar() or 0) + 1

    # 3. Create submission
    submission_id = generate_entity_id("sub")
    submission = SubmissionModel(
        id=submission_id,
        task_id=task_id,
        learner_id=learner_id,
        session_id=session_id,
        submission_type=submission_type.value,
        content=content,
        attempt_number=attempt_number
    )
    db.add(submission)
    await db.flush()

    # 4. Record event
    if event_service:
        await event_service.record(
            entity_type="submission",
            entity_id=submission_id,
            event_type=EventType.SUBMISSION_CREATED,
            actor=learner_id,
            new_value=f"attempt {attempt_number}"
        )

    # 5. Auto-validate if requested
    validation = None
    if auto_validate:
        validation = await validate_submission(
            db,
            submission_id,
            task,
            event_service=event_service
        )

    await db.commit()
    return Submission.model_validate(submission), validation
```

### Validate Submission

```python
async def validate_submission(
    db,
    submission_id: str,
    task: Optional[TaskModel] = None,
    validator_type: ValidatorType = ValidatorType.AUTOMATED,
    event_service: Optional[EventService] = None
) -> Validation:
    """
    Validate a submission against acceptance criteria.

    For MVP, this is a simple check. In production, this would:
    - Run actual tests
    - Execute code
    - Check SQL queries
    - etc.
    """
    # 1. Load submission and task
    submission = await db.get(SubmissionModel, submission_id)
    if not submission:
        raise NotFoundError(submission_id)

    if task is None:
        task = await db.get(TaskModel, submission.task_id)

    # 2. Simple validation logic (placeholder for real validation)
    passed, error_message = await run_acceptance_check(
        task.acceptance_criteria,
        submission.content,
        submission.submission_type
    )

    # 3. Create validation record
    validation_id = generate_entity_id("val")
    validation = ValidationModel(
        id=validation_id,
        submission_id=submission_id,
        task_id=task.id,
        passed=passed,
        error_message=error_message,
        validator_type=validator_type.value
    )
    db.add(validation)
    await db.flush()

    # 4. Record event
    if event_service:
        await event_service.record(
            entity_type="validation",
            entity_id=validation_id,
            event_type=EventType.VALIDATION_COMPLETED,
            actor="system",
            new_value="passed" if passed else f"failed: {error_message}"
        )

    return Validation.model_validate(validation)


async def run_acceptance_check(
    acceptance_criteria: str,
    submission_content: str,
    submission_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Run acceptance criteria check.

    This is a PLACEHOLDER. Real implementation would:
    - Parse structured acceptance criteria
    - Run tests, execute code, etc.

    For MVP, just checks that submission is non-empty.
    """
    if not submission_content or not submission_content.strip():
        return False, "Submission is empty"

    # TODO: Real validation logic here
    # For now, all non-empty submissions pass
    return True, None
```

---

## 4. Validation Interface (Future)

The validation service should be pluggable for different validation strategies:

```python
from abc import ABC, abstractmethod


class Validator(ABC):
    """Base class for validators."""

    @abstractmethod
    async def validate(
        self,
        submission: Submission,
        acceptance_criteria: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate submission against criteria.

        Returns:
            (passed, error_message)
        """
        pass


class SimpleValidator(Validator):
    """Basic non-empty check."""

    async def validate(
        self,
        submission: Submission,
        acceptance_criteria: str
    ) -> Tuple[bool, Optional[str]]:
        if not submission.content.strip():
            return False, "Submission is empty"
        return True, None


class CodeValidator(Validator):
    """Validates code submissions (future)."""

    async def validate(
        self,
        submission: Submission,
        acceptance_criteria: str
    ) -> Tuple[bool, Optional[str]]:
        # TODO: Parse AC for assertions
        # TODO: Execute code in sandbox
        # TODO: Check outputs
        pass


class SqlValidator(Validator):
    """Validates SQL queries (future)."""

    async def validate(
        self,
        submission: Submission,
        acceptance_criteria: str
    ) -> Tuple[bool, Optional[str]]:
        # TODO: Parse expected results from AC
        # TODO: Execute query against test DB
        # TODO: Compare results
        pass


# Registry for validators by submission type
VALIDATORS = {
    SubmissionType.CODE: CodeValidator(),
    SubmissionType.SQL: SqlValidator(),
    SubmissionType.TEXT: SimpleValidator(),
    SubmissionType.JUPYTER_CELL: CodeValidator(),
    SubmissionType.RESULT_SET: SimpleValidator(),
}


async def get_validator(submission_type: SubmissionType) -> Validator:
    """Get appropriate validator for submission type."""
    return VALIDATORS.get(submission_type, SimpleValidator())
```

---

## 5. Can Close Task Logic

```python
async def can_close_task(
    db,
    task_id: str,
    learner_id: str
) -> Tuple[bool, str]:
    """
    Check if a task can be closed based on validation state.

    Rules:
    - Subtasks: MUST have a passing validation
    - Tasks: Allowed (validation is feedback, not gate)
    - Epics: Allowed (no direct submissions)
    """
    task = await db.get(TaskModel, task_id)
    if not task:
        raise NotFoundError(task_id)

    # Non-subtasks can always close (validation is optional)
    if task.task_type != TaskType.SUBTASK.value:
        return True, ""

    # Subtasks require passing validation
    latest_validation = await get_latest_validation(db, task_id, learner_id)

    if latest_validation is None:
        return False, "No submission found. Submit your work before closing."

    if not latest_validation.passed:
        return False, f"Validation failed: {latest_validation.error_message}"

    return True, ""


async def get_latest_validation(
    db,
    task_id: str,
    learner_id: str
) -> Optional[Validation]:
    """
    Get the most recent validation for a task/learner.
    """
    result = await db.execute(
        select(ValidationModel)
        .join(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
        .order_by(ValidationModel.validated_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return Validation.model_validate(row) if row else None
```

---

## 6. Submission History

```python
async def get_submission_history(
    db,
    task_id: str,
    learner_id: str,
    include_validations: bool = True
) -> List[SubmissionWithValidation]:
    """
    Get full submission history with validations.
    """
    query = (
        select(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
        .order_by(SubmissionModel.attempt_number.desc())
    )

    result = await db.execute(query)
    submissions = result.scalars().all()

    output = []
    for sub in submissions:
        sub_pydantic = Submission.model_validate(sub)

        validation = None
        if include_validations:
            val_result = await db.execute(
                select(ValidationModel)
                .where(ValidationModel.submission_id == sub.id)
                .order_by(ValidationModel.validated_at.desc())
                .limit(1)
            )
            val_row = val_result.scalar_one_or_none()
            if val_row:
                validation = Validation.model_validate(val_row)

        output.append(SubmissionWithValidation(
            **sub_pydantic.model_dump(),
            validation=validation
        ))

    return output
```

---

## 7. Error Types

```python
class SubmissionError(Exception):
    """Base exception for submission operations."""
    pass


class InvalidStateError(SubmissionError):
    """Task is in invalid state for submission."""
    pass


class ValidationError(SubmissionError):
    """Validation failed."""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.details = details
        super().__init__(message)
```

---

## 8. Database Queries Reference

### Get Attempts with Validation Status

```sql
SELECT
    s.*,
    v.passed,
    v.error_message,
    v.validated_at
FROM submissions s
LEFT JOIN LATERAL (
    SELECT * FROM validations
    WHERE submission_id = s.id
    ORDER BY validated_at DESC
    LIMIT 1
) v ON true
WHERE s.task_id = :task_id
  AND s.learner_id = :learner_id
ORDER BY s.attempt_number DESC
```

### Tasks Awaiting Submission

```sql
-- Find subtasks learner hasn't submitted yet
SELECT t.*
FROM tasks t
WHERE t.project_id = :project_id
  AND t.task_type = 'subtask'
  AND t.status IN ('open', 'in_progress')
  AND NOT EXISTS (
    SELECT 1 FROM submissions s
    WHERE s.task_id = t.id
      AND s.learner_id = :learner_id
  )
ORDER BY t.priority ASC, t.created_at ASC
```

---

## 9. File Structure

```
src/ltt/services/
├── submission.py     # SubmissionService
├── validation.py     # ValidationService
├── validators/
│   ├── __init__.py
│   ├── base.py       # Validator ABC
│   ├── simple.py     # SimpleValidator
│   ├── code.py       # CodeValidator (future)
│   └── sql.py        # SqlValidator (future)
```

---

## 10. Testing Requirements

```python
class TestSubmissionService:
    async def test_create_submission_increments_attempt(self):
        """Second submission has attempt_number=2."""
        ...

    async def test_cannot_submit_to_closed_task(self):
        """Submitting to closed task raises error."""
        ...


class TestValidationService:
    async def test_empty_submission_fails(self):
        """Empty content fails validation."""
        ...

    async def test_subtask_requires_validation_to_close(self):
        """can_close_task returns False without validation."""
        ...

    async def test_task_can_close_without_validation(self):
        """Regular tasks don't require validation."""
        ...

    async def test_failed_validation_blocks_close(self):
        """can_close_task returns False if latest validation failed."""
        ...
```
