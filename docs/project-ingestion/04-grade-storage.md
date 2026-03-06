# Phase 04: Grade Storage on Validations

> Store numeric grades locally, not just binary pass/fail.

**Status**: Not started
**Depends on**: Phase 02 (`max_grade` column), Phase 03 (grade passback wired)
**Unblocks**: Phase 07

---

## Current State

Validation is binary — `passed: bool` with no numeric score:

```
services/ltt-core/src/ltt/models/validation.py
  ValidationBase (line ~35):
    passed: bool
    error_message: str | None
    validator_type: ValidatorType    # "automated" | "manual"

  ValidationModel (line 63):
    id, submission_id, task_id, passed, error_message, validator_type, validated_at
```

The `validate_submission()` function in `validation_service.py` (line 43) uses `SimpleValidator` — a non-empty check that returns `True`/`False`. No numeric score.

Progress calculation in `get_progress()` counts `completed_tasks / total_tasks` — all tasks weighted equally regardless of `max_grade`.

---

## Changes

### Model Changes

| Field | Type | Default | Where | Notes |
|-------|------|---------|-------|-------|
| `grade` | `Float` | `None` | `ValidationBase`, `Validation`, `ValidationModel` | 0.0–1.0 normalised score |
| `grader_type` | `String(20)` | `'auto'` | `ValidationBase`, `Validation`, `ValidationModel` | `"auto"` / `"llm"` / `"manual"` |
| `feedback` | `Text` | `None` | `ValidationBase`, `Validation`, `ValidationModel` | Grader's explanation |

### Migration

```sql
ALTER TABLE validations ADD COLUMN grade FLOAT;
ALTER TABLE validations ADD COLUMN grader_type VARCHAR(20) DEFAULT 'auto';
ALTER TABLE validations ADD COLUMN feedback TEXT;
```

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `services/ltt-core/src/ltt/services/validation_service.py` | `validate_submission()` ~line 43 | Set `grade=1.0` on pass, `grade=0.0` on fail (simple mode) |
| `services/ltt-core/src/ltt/services/validation_service.py` | `validate_submission()` ~line 43 | Set `grader_type="auto"` (already the default) |

### Grade Passback Update

| File | Function | Change |
|------|----------|--------|
| `services/api-server/src/api/lti/grades.py` | `maybe_send_grade()` ~line 99 | When `max_grade` is set on tasks, compute weighted score instead of simple `completed/total` |

**Weighted grading formula** (future enhancement, not required for this phase):
```
score = sum(task.max_grade * avg_subtask_grade for task in completed_tasks)
max_score = sum(task.max_grade for task in all_tasks)
```

For this phase, keep the simple `completed/total` approach but store `grade` on each validation for future use.

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/models/validation.py` | Add `grade`, `grader_type`, `feedback` to `ValidationBase` | ~35 |
| `services/ltt-core/src/ltt/models/validation.py` | Add columns to `ValidationModel` | ~63–87 |
| `services/ltt-core/src/ltt/db/migrations/versions/` | New migration file | New |
| `services/ltt-core/src/ltt/services/validation_service.py` | Set grade on validation creation | ~78–90 |
| `services/ltt-core/tests/` | Test grade storage | New/updated tests |

---

## Test Plan

### New Tests

- `test_validation_stores_grade_on_pass` — Submit valid content, verify `validation.grade == 1.0` and `grader_type == "auto"`.
- `test_validation_stores_grade_on_fail` — Submit empty/invalid content, verify `validation.grade == 0.0`.
- `test_validation_feedback_stored` — When feedback is provided, verify it's persisted.
- `test_grade_defaults_to_none_for_legacy` — Existing validations (before migration) have `grade=None`. Verify they still work.

### Updated Tests

- Existing validation tests in `services/ltt-core/tests/` — add assertions for `grade` field in returned `Validation` objects.

### Run

```bash
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head
uv run pytest services/ltt-core/tests/ -v -k "validation"
```

---

## Verification

```bash
# 1. Run migration
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head

# 2. Verify columns
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "\d validations" | grep -E "grade|grader_type|feedback"

# 3. Submit work and check grade
# (Use CLI or API to create submission, then check)
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "SELECT id, passed, grade, grader_type, feedback FROM validations LIMIT 5;"

# 4. Run tests
uv run pytest services/ltt-core/tests/ -v -k "validation or grade"
```

---

## Notes

- `grade` is normalised 0.0–1.0, not raw points. To get raw points: `grade * task.max_grade`.
- The `grader_type` field distinguishes auto (rule-based), LLM (Claude-graded), and manual (instructor override). Only `"auto"` is implemented in this phase.
- `feedback` is intended for LLM or manual grading explanations. Auto grading can optionally set it to `"Passed: non-empty submission"` or similar.
- Future grading strategies (LLM-based, rubric-based, test-based) are detailed in [grading.md](grading.md) — this phase just adds the storage layer.
