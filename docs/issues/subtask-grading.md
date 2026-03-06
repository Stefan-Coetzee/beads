# Add grading to subtask submissions

## Summary

Subtasks currently have binary pass/fail validation. We need numeric grading at the subtask level, with grades propagated up to the LMS via LTI AGS on each successful submission. Task-level `max_grade` defines the ceiling for its children.

## Current State

- **Validation**: `Validation.passed` is a boolean — no numeric score
- **Progress**: Calculated as `completed_tasks / total_tasks` — all tasks count equally
- **AGS infrastructure**: `lti/grades.py` has `send_grade()` and `maybe_send_grade()` — fully functional but **never called**
- **Missing link**: `submit()` in `ltt/tools/progress.py` closes tasks but never triggers grade passback
- **No grade storage**: No `score`, `grade`, or `points` field in the database

## Requirements

### 1. Grade field on subtask submissions

When a submission passes validation, store a numeric grade:

```python
# On Validation model (or new GradeRecord)
grade: float          # 0.0 – 1.0 normalised score
grader_type: str      # "auto" | "llm" | "manual"
feedback: str | None  # Grader's explanation
```

The grading strategy is TBD — options include:
- **Simple**: pass = 1.0, fail = 0.0 (current behavior, just explicit)
- **LLM-graded**: Claude evaluates submission quality against acceptance_criteria
- **Rubric-based**: Acceptance criteria items scored individually, averaged
- **Test-based**: Run submitted code against test cases, score = pass_rate

### 2. `max_grade` on tasks

Tasks define the point ceiling for their subtasks:

```json
{
  "title": "Write WHERE query for long queues",
  "task_type": "task",
  "max_grade": 10,
  "subtasks": [
    {"title": "Consider the human impact", "subtask_type": "conversational"},
    {"title": "Write the SQL query", "subtask_type": "exercise"}
  ]
}
```

How `max_grade` distributes across subtasks is TBD. Options:
- Equal split across exercise subtasks (conversational = 0 weight)
- Explicit `weight` per subtask
- All points on the "main" exercise, rest are engagement

### 3. Wire grade passback into submit flow

```python
# In submit() tool, after close_task() succeeds:
progress = await get_progress(session, learner_id, project_id)
await maybe_send_grade(
    learner_id=learner_id,
    project_id=project_id,
    completed=progress.completed_tasks,
    total=progress.total_tasks,
    storage=get_launch_data_storage(),
)
```

This is the minimum — just wire the existing infrastructure. Weighted grading comes later.

### 4. Conversational vs exercise distinction

`subtask_type` must be added to the model and DB (currently in JSON but dropped on ingest):

- **`exercise`**: Requires submission + validation, earns grade points
- **`conversational`**: Engagement checkpoint, no submission required, zero grade weight

### 5. Grade persistence

Store grades locally (not just in the LMS) for:
- Instructor dashboards
- Analytics
- Retry/regrade scenarios
- LMS reconnection after session expiry

## Schema Changes

```sql
-- New columns on tasks
ALTER TABLE tasks ADD COLUMN subtask_type VARCHAR(20) DEFAULT 'exercise';
ALTER TABLE tasks ADD COLUMN max_grade FLOAT;
ALTER TABLE tasks ADD COLUMN narrative BOOLEAN DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN tutor_config JSONB;  -- project-level only

-- New columns on validations (or new table)
ALTER TABLE validations ADD COLUMN grade FLOAT;
ALTER TABLE validations ADD COLUMN grader_type VARCHAR(20) DEFAULT 'auto';
ALTER TABLE validations ADD COLUMN feedback TEXT;
```

## Ingest Changes

`ingest.py` must pass through:
- `project_id` / `version` / `version_tag` (stable identity — already in ProjectSchema, not yet used by ingest)
- `subtask_type` (currently dropped)
- `max_grade` (new field on tasks)
- `narrative` + `tutor_config` (new project-level fields)
- `estimated_minutes` (currently dropped — needed for time-based analytics)
- `priority` for epics (currently dropped)

## Implementation Order

1. **Add `subtask_type` + `narrative` + `tutor_config` to model + DB + ingest** — unblocks everything else
2. **Fix ingest drops** — pass through `estimated_minutes`, epic `priority`
3. **Wire `maybe_send_grade()` into submit flow** — immediate value, binary grading
4. **Add `max_grade` to model + DB + ingest** — enables weighted grading
5. **Add grade storage on validations** — persist scores locally
6. **Implement grading strategies** — LLM-based, rubric-based, etc.

## Context

- Ingestion service: `services/ltt-core/src/ltt/services/ingest.py`
- Submit tool: `services/ltt-core/src/ltt/tools/progress.py`
- Grade passback: `services/api-server/src/api/lti/grades.py`
- Validation service: `services/ltt-core/src/ltt/services/validation_service.py`
- Task model: `services/ltt-core/src/ltt/models/task.py`
