# ADR-001: Learner-Scoped Task Progress (Two-Layer Architecture)

**Status**: Accepted
**Date**: 2024

---

## Context

LTT needs to support thousands of learners working through the same project (curriculum) simultaneously. Each learner has independent progress, but the curriculum itself is shared.

The naive approach — giving each learner a full copy of the task tree — creates data duplication, makes curriculum updates painful (must propagate to all copies), and wastes storage.

## Decision

Separate **template** data (shared curriculum) from **instance** data (per-learner state) into two layers:

### Template Layer (shared across all learners)

| Table | Purpose |
|-------|---------|
| `tasks` | Project structure, descriptions, acceptance criteria |
| `learning_objectives` | Bloom's taxonomy objectives |
| `dependencies` | Task relationships and blocking |
| `content` | Learning materials |

### Instance Layer (per-learner)

| Table | Purpose |
|-------|---------|
| `learner_task_progress` | Status (open/in_progress/blocked/closed) |
| `submissions` | Learner's work |
| `validations` | Pass/fail results |
| `status_summaries` | Progress notes |

Tasks have NO `status` field. Status lives exclusively in `learner_task_progress`, keyed by `(task_id, learner_id)`.

### Lazy Initialization

Progress records are created on first access, not upfront:

```python
progress = await get_or_create_progress(session, task_id, learner_id)
# Creates record with status='open' if it doesn't exist
```

In SQL queries, `COALESCE(ltp.status, 'open')` treats missing records as `open`.

## Consequences

### Positive
- One curriculum serves unlimited learners
- Curriculum updates take effect immediately for all learners
- Storage scales linearly with actual progress, not with `learners * tasks`
- Clean separation of concerns

### Negative
- All status queries MUST join with `learner_task_progress` — cannot query `task.status`
- PostgreSQL ARRAY fields on tasks require new-list assignment for mutation detection
- Slightly more complex queries

### Invariant

```python
# WRONG - tasks have no status
task.status  # AttributeError

# CORRECT - status is per-learner
progress = await get_or_create_progress(session, task_id, learner_id)
progress.status  # 'open', 'in_progress', 'blocked', 'closed'
```
