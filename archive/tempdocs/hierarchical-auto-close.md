# Hierarchical Auto-Close Feature

**Status**: Proposed
**Date**: 2026-01-04
**Related**: [ADR-002](../../python-port/docs/adr/002-submission-driven-task-completion.md)

---

## Problem Statement

When the agent completes all subtasks under a task, the parent task remains open. The agent then sees the project and epic as "ready work" instead of the next logical task.

**Example from simulation:**
```json
{
  "message": "Validation successful, task complete!",
  "ready_tasks": [
    {"id": "proj-9b46", "title": "Maji Ndogo Water Crisis...", "status": "open"},
    {"id": "proj-9b46.1", "title": "Introduction", "status": "open"},
    {"id": "proj-9b46.1.1", "title": "Understand the mission", "status": "open"}
  ]
}
```

The agent completed all 3 subtasks under `proj-9b46.1.1`, but the task itself is still "open", causing confusion about what to do next.

---

## Current Behavior (ADR-002)

From ADR-002 Section 2:

> **Hierarchical Cascade is EXPLICIT**
>
> When all children of a task/epic close, the parent does NOT auto-close. The agent must explicitly close the parent.

**Current validation rules** (`validation_service.py:can_close_task`):
- **Subtasks**: MUST have passing validation to close
- **Tasks/Epics/Projects**: Can close without validation (validation is optional)

---

## Proposed Changes

### 1. Add `requires_submission` Flag to Task Model

Add a boolean flag to indicate whether a task requires a submission to close.

**Schema Change:**

```python
# src/ltt/models/task.py

class TaskBase(BaseModel):
    # ... existing fields ...

    requires_submission: bool = Field(
        default=None,  # None = use default based on task_type
        description="Whether this task requires a submission to close. "
                    "Default: True for subtasks, False for tasks/epics/projects"
    )

class TaskModel(Base, TimestampMixin):
    # ... existing fields ...

    requires_submission: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=None
    )
```

**Default Behavior:**
| Task Type | Default `requires_submission` | Behavior |
|-----------|------------------------------|----------|
| subtask   | `True`  | Must submit to close |
| task      | `False` | Auto-closes when children close |
| epic      | `False` | Auto-closes when children close |
| project   | `False` | Auto-closes when children close |

**Override Capability:**
- Set `requires_submission=True` on a task to require submission before closing
- Set `requires_submission=False` on a subtask to allow it to auto-close (rare)

---

### 2. Implement Hierarchical Auto-Close

When a task closes, check if all siblings are closed. If so, attempt to close the parent. Recurse upward.

**New Function: `try_auto_close_ancestors()`**

```python
# src/ltt/services/progress_service.py

async def try_auto_close_ancestors(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> list[str]:
    """
    After a task closes, check if parent(s) can auto-close.

    Returns list of task IDs that were auto-closed (bottom-up order).
    """
    auto_closed = []

    # Get the task that just closed
    task = await get_task(session, task_id)
    if not task or not task.parent_id:
        return auto_closed

    current_parent_id = task.parent_id

    while current_parent_id:
        parent = await get_task(session, current_parent_id)
        if not parent:
            break

        # Check if parent requires submission
        requires_sub = _get_requires_submission(parent)
        if requires_sub:
            break  # Parent needs explicit submission, stop climbing

        # Check if all children are closed
        children = await get_children(session, current_parent_id)
        all_closed = True

        for child in children:
            progress = await get_or_create_progress(session, child.id, learner_id)
            if progress.status != TaskStatus.CLOSED.value:
                all_closed = False
                break

        if not all_closed:
            break  # Not all children closed, stop climbing

        # Auto-close this parent
        try:
            await close_task(session, current_parent_id, learner_id, "Auto-closed: all children complete")
            auto_closed.append(current_parent_id)
            current_parent_id = parent.parent_id  # Continue climbing
        except InvalidStatusTransitionError:
            break  # Can't close, stop climbing

    return auto_closed


def _get_requires_submission(task: Task) -> bool:
    """Determine if task requires submission based on flag or default."""
    if task.requires_submission is not None:
        return task.requires_submission
    # Default based on task type
    return task.task_type == TaskType.SUBTASK.value
```

**Order Guarantee:**
- Process bottom-up: subtask → task → epic → project
- Stop at first parent that can't close
- Return list in closure order (first closed → last closed)

---

### 3. Update `submit()` to Report Auto-Closed Tasks

**Schema Change:**

```python
# src/ltt/tools/schemas.py

class AutoClosedTask(BaseModel):
    """A task that was auto-closed due to children completing."""
    id: str
    title: str
    task_type: str

class SubmitOutput(BaseModel):
    success: bool
    submission_id: str
    attempt_number: int
    validation_passed: bool | None
    validation_message: str | None
    status: str
    message: str
    ready_tasks: list[TaskSummaryOutput] | None = None
    auto_closed: list[AutoClosedTask] | None = None  # NEW
```

**Updated `submit()` Flow:**

```python
# src/ltt/tools/progress.py

async def submit(input: SubmitInput, learner_id: str, session: AsyncSession) -> SubmitOutput:
    # ... existing validation logic ...

    auto_closed_list = None

    if validation.passed:
        try:
            closed_progress = await close_task(
                session, input.task_id, learner_id, "Passed validation"
            )
            current_status = closed_progress.status
            message = "Validation successful, task complete!"

            # NEW: Try to auto-close ancestors
            auto_closed_ids = await try_auto_close_ancestors(
                session, input.task_id, learner_id
            )

            if auto_closed_ids:
                # Fetch details for auto-closed tasks
                auto_closed_list = []
                for aid in auto_closed_ids:
                    t = await get_task(session, aid)
                    if t:
                        auto_closed_list.append(AutoClosedTask(
                            id=t.id,
                            title=t.title,
                            task_type=t.task_type,
                        ))

                # Update message
                closed_names = ", ".join([t.title for t in auto_closed_list])
                message = f"Validation successful, task complete! Also completed: {closed_names}"

            # Get ready tasks (existing logic)
            ready_tasks = await get_ready_work(...)

        except InvalidStatusTransitionError as e:
            message = f"Validation passed, but task cannot close yet: {e}"
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
        auto_closed=auto_closed_list,  # NEW
    )
```

---

### 4. Example Output After Implementation

**Before (current):**
```json
{
  "message": "Validation successful, task complete!",
  "status": "closed",
  "auto_closed": null,
  "ready_tasks": [
    {"id": "proj-9b46", "status": "open"},
    {"id": "proj-9b46.1", "status": "open"},
    {"id": "proj-9b46.1.1", "status": "open"}
  ]
}
```

**After (proposed):**
```json
{
  "message": "Validation successful, task complete! Also completed: Understand the mission, Introduction",
  "status": "closed",
  "auto_closed": [
    {"id": "proj-9b46.1.1", "title": "Understand the mission", "task_type": "task"},
    {"id": "proj-9b46.1", "title": "Introduction", "task_type": "epic"}
  ],
  "ready_tasks": [
    {"id": "proj-9b46.2", "title": "Get to Know the Data", "status": "open", "task_type": "epic"},
    {"id": "proj-9b46.2.1", "title": "Explore the database", "status": "open", "task_type": "task"}
  ]
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/ltt/models/task.py` | Add `requires_submission` field |
| `src/ltt/models/__init__.py` | Export updated models |
| `src/ltt/services/progress_service.py` | Add `try_auto_close_ancestors()` |
| `src/ltt/services/validation_service.py` | Update `can_close_task()` to respect flag |
| `src/ltt/tools/schemas.py` | Add `AutoClosedTask`, update `SubmitOutput` |
| `src/ltt/tools/progress.py` | Call `try_auto_close_ancestors()` in `submit()` |
| `src/ltt/services/ingest.py` | Handle `requires_submission` in JSON ingestion |

---

## Migration

### Database Migration

```python
# alembic/versions/xxx_add_requires_submission.py

def upgrade():
    op.add_column('tasks', sa.Column('requires_submission', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('tasks', 'requires_submission')
```

### Data Migration

Existing tasks: `requires_submission = NULL` (use default behavior based on task_type)

---

## JSON Schema Update

```json
{
  "title": "Subtask with submission requirement",
  "task_type": "subtask",
  "requires_submission": true,  // optional, defaults to true for subtasks
  ...
}

{
  "title": "Task that requires summary submission",
  "task_type": "task",
  "requires_submission": true,  // override: require submission for this task
  ...
}
```

---

## Test Cases

### 1. Auto-close parent task when all subtasks complete
```python
async def test_auto_close_parent_task():
    # Given: task with 2 subtasks
    # When: both subtasks close via submit
    # Then: parent task auto-closes
    pass
```

### 2. Auto-close epic when all tasks complete
```python
async def test_auto_close_epic():
    # Given: epic with 2 tasks, each with subtasks
    # When: all subtasks and tasks close
    # Then: epic auto-closes
    pass
```

### 3. Don't auto-close task with requires_submission=True
```python
async def test_no_auto_close_when_submission_required():
    # Given: task with requires_submission=True and 2 subtasks
    # When: both subtasks close
    # Then: parent task stays in_progress (needs submission)
    pass
```

### 4. Submit output includes auto-closed tasks
```python
async def test_submit_reports_auto_closed():
    # Given: subtask that is last child
    # When: submit with passing validation
    # Then: output.auto_closed contains parent task
    pass
```

### 5. Ready tasks updated correctly after auto-close
```python
async def test_ready_tasks_after_auto_close():
    # Given: Epic 1 blocked Epic 2
    # When: last task in Epic 1 closes, Epic 1 auto-closes
    # Then: ready_tasks includes Epic 2 tasks
    pass
```

---

## Consequences

### Benefits

1. **Agent sees correct next steps**: Ready tasks shows actual next work, not parent containers
2. **Less cognitive load**: Agent doesn't need to track when to close parents
3. **Configurable**: `requires_submission` allows tasks that need explicit completion
4. **Backward compatible**: Existing data uses sensible defaults

### Trade-offs

1. **Less explicit control**: Parents close automatically (mitigated by `requires_submission` flag)
2. **Database write on cascade**: Multiple status updates when hierarchy closes
3. **Slight complexity**: New function to maintain

---

## Decision Checklist

- [ ] Approve design
- [ ] Create migration for `requires_submission`
- [ ] Implement `try_auto_close_ancestors()`
- [ ] Update `submit()` output
- [ ] Update ingestion to handle flag
- [ ] Add tests
- [ ] Update ADR-002 with addendum

---

## Related

- [ADR-002: Submission-Driven Task Completion](../../python-port/docs/adr/002-submission-driven-task-completion.md)
- [ADR-001: Learner-Scoped Task Progress](../../python-port/docs/adr/001-learner-scoped-task-progress.md)
