# ADR-002: Submission-Driven Task Completion

**Status**: Proposed
**Date**: 2026-01-01
**Deciders**: Stefan Coetzee
**Related**: [GitHub Issue #835](https://github.com/steveyegge/beads/issues/835)

---

## Context

The current workflow requires two steps to complete a task:

```python
# Current: Two-step completion
result = await submit(task_id, content, "code")
if result.validation_passed:
    await close_task(session, task_id, learner_id, "Completed")  # Extra step
```

For a submission-driven learning system, this is unnecessary friction. When a learner submits work that passes validation, the task should complete automatically.

### Questions to Resolve

1. Should tasks auto-close when validation passes?
2. Should parent tasks auto-close when all children close?
3. What happens to submissions when a task is reopened?
4. How do dependents get unblocked?

---

## Decision

### 1. Auto-Close on Successful Validation (Default Behavior)

When `submit()` is called and validation passes, the task closes automatically.

**Call Flow:**

```
submit()
  │
  ├── create_submission()      # Record the work
  │
  ├── validate_submission()    # Check acceptance criteria
  │       │
  │       └── Returns: passed=True/False
  │
  └── IF validation.passed:
        │
        └── close_task()       # Reuse existing function
              │
              └── update_status()  # Validates transition, checks children
                    │
                    ├── can_close_task()     # Validation requirements
                    ├── Check children closed
                    └── Set status = 'closed'
```

**Key point**: No new functions. `submit()` simply calls existing `close_task()` after successful validation.

### 2. Hierarchical Cascade is EXPLICIT

When all children of a task/epic close, the parent does NOT auto-close. The agent must explicitly close the parent.

**Rationale:**
- Parent completion may require review/summary beyond child completion
- Agent maintains control over workflow pacing
- Simpler mental model: "I close things explicitly"

**Example:**
```python
# All subtasks passed validation and auto-closed
# Parent task still in_progress
# Agent reviews, then:
await close_task(session, parent_task_id, learner_id, "All subtasks complete")
```

### 3. Submissions are Preserved on Reopen

When `go_back()` reopens a task, submissions remain in the database.

**Rationale:**
- Submissions are historical record (audit trail)
- Learner may want to see previous attempts
- `attempt_number` tracks submission history
- New submission after reopen gets incremented attempt_number

**Behavior:**
```python
await go_back(task_id, "Need to revise approach")
# Task reopened: status = 'open'
# Previous submissions: still exist (attempt_number 1, 2, ...)
# Latest validation: still references last submission

await submit(task_id, new_content, "code")
# New submission created with attempt_number = previous + 1
# New validation runs
# If passes, task auto-closes again
```

### 4. Unblocking is Dynamic (Already Works)

When a task closes, dependent tasks are NOT explicitly "unblocked". Instead, `get_ready_work()` dynamically queries current status.

**How it works:**
```sql
-- get_ready_work() query checks blocker status at query time
WHERE COALESCE(ltp_blocker.status, 'open') != 'closed'
```

When blocker closes, the next `get_ready_work()` call returns newly unblocked tasks. No explicit unblock step needed.

---

## Call Flow Summary

```
Agent Workflow
==============

1. get_ready() ──────────────────────────────► Returns unblocked tasks
                                                (in_progress first, then open)

2. start_task() ─┬─ get_or_create_progress()
                 ├─ is_task_blocked()
                 └─ update_status(IN_PROGRESS)

3. submit() ─────┬─ create_submission()
                 ├─ validate_submission()
                 │     └─ SimpleValidator.validate()
                 │
                 └─ IF passed: close_task()
                       └─ update_status(CLOSED)
                             ├─ can_close_task()    # Subtasks need validation
                             └─ Check children      # Tasks/epics need children closed

4. go_back() ────┬─ Check task is closed
                 └─ reopen_task()
                       └─ update_status(OPEN)


Service Layer Dependencies
==========================

submit() ──────────────────► close_task()
                                  │
close_task() ──────────────► update_status()
                                  │
update_status() ───────────► can_close_task()  (validation_service)
                             get_children()     (task_service, implicit)

go_back() ─────────────────► reopen_task()
                                  │
reopen_task() ─────────────► update_status()
```

---

## Schema Changes

### SubmitOutput (tools/schemas.py)

```python
# Before
class SubmitOutput(BaseModel):
    success: bool
    submission_id: str
    attempt_number: int
    validation_passed: bool | None
    validation_message: str | None
    can_close_task: bool        # REMOVE: Redundant with status
    message: str

# After
class SubmitOutput(BaseModel):
    success: bool
    submission_id: str
    attempt_number: int
    validation_passed: bool | None
    validation_message: str | None
    status: str                  # ADD: Current status after submission
    message: str
```

### Messages

| Scenario | Message |
|----------|---------|
| Validation passed, auto-closed | "Validation successful, task complete" |
| Validation passed, children open | "Validation successful" (status stays in_progress) |
| Validation failed | "Validation failed: {error_message}" |

---

## Files Affected

| File | Changes |
|------|---------|
| `src/ltt/tools/schemas.py` | Replace `can_close_task` with `status` |
| `src/ltt/tools/progress.py` | Call `close_task()` after successful validation |
| `tests/tools/test_progress.py` | Update tests for auto-close behavior |

---

## Consequences

### Benefits

1. **Simpler agent workflow**: Submit → done (one step, not two)
2. **No new functions**: Reuses existing `close_task()` logic
3. **Consistent behavior**: All tasks follow same submit→validate→close flow
4. **History preserved**: Submissions remain after reopen

### Trade-offs

1. **Less explicit control**: Agent can't submit without closing (use case: "save draft")
2. **Parent still needs explicit close**: Agent must track when children complete

### Mitigations

- For "save draft" use case: Could add `draft: bool` parameter to submit (future)
- For parent tracking: `get_ready()` shows parent tasks when children complete

---

## References

- [ADR-001](./001-learner-scoped-task-progress.md) - Two-layer architecture
- [GitHub Issue #835](https://github.com/steveyegge/beads/issues/835) - Original feature request
- [04-submissions-validation.md](../04-submissions-validation.md) - Validation flow
