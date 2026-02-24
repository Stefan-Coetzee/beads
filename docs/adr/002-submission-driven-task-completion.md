# ADR-002: Submission-Driven Task Completion

**Status**: Accepted
**Date**: 2024

---

## Context

In a tutoring system, learners should not manually mark tasks as "done." Completion must be verified through submitted work. But not every level of the hierarchy needs a submission — epics and projects are organizational containers.

## Decision

Task completion is driven by validation, not explicit close calls:

```
submit() → validate() → if PASS → close_task() → try_auto_close_ancestors()
```

### Rules

1. **Subtasks** require a passing validation to close (`requires_submission = true` by default)
2. **Tasks, Epics, Projects** auto-close when all children are closed (`requires_submission = false` by default)
3. The `requires_submission` flag can override defaults (e.g., a task that needs explicit submission)

### Hierarchical Auto-Close

When a subtask closes, the system checks upward:

```
Subtask closes (validation passed)
  → Are all sibling subtasks closed?
    → Yes: auto-close parent Task
      → Are all sibling Tasks closed?
        → Yes: auto-close parent Epic
          → Are all Epics closed?
            → Yes: auto-close Project
```

The `submit()` tool returns which ancestors were auto-closed:

```python
result = await submit(...)
result.status       # "closed"
result.auto_closed  # ["proj-123.1.2", "proj-123.1"]  (parent task, epic)
```

### Validation

- Current: `SimpleValidator` (non-empty check)
- Future: Custom validators (SQL result checks, code tests, etc.)
- Validation is triggered automatically on submission — no separate validate step

## Consequences

### Positive
- Learners can't skip work — completion requires evidence
- Natural flow: submit → feedback → resubmit if failed
- Hierarchical auto-close eliminates manual bookkeeping
- Single `submit()` tool handles the entire completion flow

### Negative
- Every subtask needs a submission to close (by design)
- Auto-close is all-or-nothing per parent — can't partially close
- `go_back()` on a parent doesn't reopen children (intentional — learner reopens specific work)
