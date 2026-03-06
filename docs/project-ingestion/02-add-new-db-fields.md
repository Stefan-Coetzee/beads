# Phase 02: Add New Fields to Model + DB + Ingest

> Add fields that exist in the JSON schema but have no corresponding DB column.

**Status**: Not started
**Depends on**: Phase 01 (TaskCreate additions)
**Unblocks**: Phase 03, Phase 04, Phase 05, Phase 06, Phase 07

---

## Current State

Four fields exist in `ProjectSchema` / `TaskSchema` / `SubtaskSchema` but have no DB column:

| Field | Schema location | On TaskModel? | On TaskCreate? |
|-------|----------------|---------------|----------------|
| `subtask_type` | `SubtaskSchema` line 91 | No | No |
| `narrative` (bool) | `ProjectSchema` line 167 | No | No |
| `tutor_config` (JSONB) | `ProjectSchema` line 174 | No | No |
| `max_grade` | `TaskSchema` line 121 | No | No |
| `project_slug` | `ProjectSchema` line 154 (as `project_id`) | No | No |

Each gets its own sub-phase below. All share a single Alembic migration.

---

## 2a. Add `subtask_type`

**Purpose**: Distinguish conversational subtasks (engagement checkpoints, no submission required) from exercise subtasks (require submission + validation, earn grade points).

### Model Changes

| Field | Type | Default | Where |
|-------|------|---------|-------|
| `subtask_type` | `String(20)` | `'exercise'` | `TaskBase`, `TaskCreate`, `TaskModel` |

### Migration

```sql
ALTER TABLE tasks ADD COLUMN subtask_type VARCHAR(20) DEFAULT 'exercise';
```

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_task()` ~line 326 | Add `subtask_type=data.get("subtask_type", "exercise")` to TaskCreate |

### Impact

- Tutor agent can check `subtask_type` to decide whether to request submission or just guide a conversation
- `can_close_task()` can skip validation for `conversational` subtasks (future enhancement)
- Grade calculation can weight `conversational` subtasks at zero (Phase 04)

---

## 2b. Add `narrative` + `tutor_config`

**Purpose**: Project-level flags for the tutor agent. `narrative=True` means the project uses a storyline. `tutor_config` is a structured object replacing the flat `tutor_persona` string.

### Model Changes

| Field | Type | Default | Where | Notes |
|-------|------|---------|-------|-------|
| `narrative` | `Boolean` | `False` | `TaskBase`, `TaskCreate`, `TaskModel` | Project level only |
| `tutor_config` | `JSONB` | `None` | `TaskBase`, `TaskCreate`, `TaskModel` | Project level only |

### Migration

```sql
ALTER TABLE tasks ADD COLUMN narrative BOOLEAN DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN tutor_config JSONB;
```

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_project_file()` ~line 122 | Add `narrative=data.get("narrative", False)` |
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_project_file()` ~line 122 | Add `tutor_config=data.get("tutor_config")` |

### Schema Reference

`TutorConfig` from `project_schema.py` (lines 73–79):
```python
class TutorConfig(BaseModel):
    persona: str | None = None
    teaching_style: TeachingStyle | None = None       # "socratic" | "direct" | "scaffolded"
    encouragement_level: EncouragementLevel | None = None  # "minimal" | "moderate" | "enthusiastic"
```

### Impact

- Tutor agent reads `tutor_config` from DB instead of relying on the flat `tutor_persona` string
- `narrative=True` signals the agent to weave narrative context into responses
- `tutor_persona` (existing field) remains for backward compatibility

---

## 2c. Add `max_grade`

**Purpose**: Tasks define the point ceiling for their subtasks. Enables weighted grading in Phase 04.

### Model Changes

| Field | Type | Default | Where | Notes |
|-------|------|---------|-------|-------|
| `max_grade` | `Float` | `None` | `TaskBase`, `TaskCreate`, `TaskModel` | Task level primarily, but allowed on any type |

### Migration

```sql
ALTER TABLE tasks ADD COLUMN max_grade FLOAT;
```

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_task()` ~line 326 | Add `max_grade=data.get("max_grade")` |

### Impact

- Grade passback (Phase 03–04) can use `max_grade` for weighted scoring
- Tasks without `max_grade` continue to use binary pass/fail (1.0 / 0.0)

---

## 2d. Add `project_slug`

**Purpose**: Store the author-defined stable identifier from the JSON `project_id` field. The existing `project_id` column on TaskModel stores the auto-generated internal ID (`proj-XXXX`). We need a separate column for the stable slug.

### Model Changes

| Field | Type | Default | Where | Notes |
|-------|------|---------|-------|-------|
| `project_slug` | `String(64)` | `None` | `TaskBase`, `TaskCreate`, `TaskModel` | Project level only |

### Migration

```sql
ALTER TABLE tasks ADD COLUMN project_slug VARCHAR(64);
CREATE UNIQUE INDEX ix_tasks_project_slug_version ON tasks (project_slug, version)
    WHERE task_type = 'project';
```

The partial unique index ensures no two projects share the same `(slug, version)` pair, while allowing the column to be `NULL` on non-project tasks.

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_project_file()` ~line 122 | Add `project_slug=data.get("project_id")` |
| `services/ltt-core/src/ltt/services/task_service.py` | New function | Add `get_project_by_slug()` (see Phase 05) |

### Why `project_slug` not `project_id`?

The `project_id` column already exists on every task row — it stores the internal ID of the root project (e.g., `proj-a1b2`). The author-defined slug is a different concept. Using `project_slug` avoids ambiguity. In the JSON and API, the field is still called `project_id`.

### Impact

- Projects retrievable by stable slug (Phase 05)
- LTI custom parameter `project_id` maps directly to this slug
- Re-ingestion can detect existing slugs (Phase 06)

---

## Combined Migration

All five new columns in a single Alembic migration:

```python
"""add subtask_type, narrative, tutor_config, max_grade, project_slug to tasks

Revision ID: [auto-generated]
Revises: b4e8c2a13f91
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    op.add_column("tasks", sa.Column("subtask_type", sa.String(20), server_default="exercise"))
    op.add_column("tasks", sa.Column("narrative", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("tasks", sa.Column("tutor_config", JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("max_grade", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("project_slug", sa.String(64), nullable=True))
    op.create_index(
        "ix_tasks_project_slug_version",
        "tasks",
        ["project_slug", "version"],
        unique=True,
        postgresql_where=sa.text("task_type = 'project'"),
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_project_slug_version", table_name="tasks")
    op.drop_column("tasks", "project_slug")
    op.drop_column("tasks", "max_grade")
    op.drop_column("tasks", "tutor_config")
    op.drop_column("tasks", "narrative")
    op.drop_column("tasks", "subtask_type")
```

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/models/task.py` | Add `subtask_type`, `narrative`, `tutor_config`, `max_grade`, `project_slug` to `TaskBase` | ~52–99 |
| `services/ltt-core/src/ltt/models/task.py` | Add same fields to `TaskModel` (SQLAlchemy columns) | ~175–283 |
| `services/ltt-core/src/ltt/db/migrations/versions/` | New migration file | New |
| `services/ltt-core/src/ltt/services/ingest.py` | Pass `subtask_type` in `ingest_task()` | ~326–340 |
| `services/ltt-core/src/ltt/services/ingest.py` | Pass `narrative`, `tutor_config`, `project_slug` in `ingest_project_file()` | ~122–134 |
| `services/ltt-core/src/ltt/services/ingest.py` | Pass `max_grade` in `ingest_task()` | ~326–340 |
| `services/ltt-core/tests/services/test_ingest.py` | New tests for all five fields | New |

---

## Test Plan

### New Tests

- `test_ingest_subtask_type` — Ingest project with `subtask_type: "conversational"` on a subtask. Verify stored value.
- `test_ingest_subtask_type_defaults_to_exercise` — Omit `subtask_type`. Verify default is `"exercise"`.
- `test_ingest_narrative_and_tutor_config` — Ingest project with `narrative: true` and `tutor_config: {persona: "Dr. Amara", teaching_style: "socratic"}`. Verify both stored.
- `test_ingest_max_grade` — Ingest task with `max_grade: 10`. Verify stored. Ingest task without — verify `None`.
- `test_ingest_project_slug` — Ingest project with `project_id: "maji-ndogo-part1"`. Verify `project_slug == "maji-ndogo-part1"` in DB.
- `test_project_slug_unique_per_version` — Ingest two projects with same slug and same version. Verify DB rejects the second (IntegrityError).

### Run

```bash
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head
uv run pytest services/ltt-core/tests/services/test_ingest.py -v
```

---

## Verification

```bash
# 1. Run migration
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head

# 2. Verify columns exist
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "\d tasks" | grep -E "subtask_type|narrative|tutor_config|max_grade|project_slug"

# 3. Ingest test project
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json

# 4. Check values
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "SELECT id, task_type, subtask_type, narrative, max_grade, project_slug FROM tasks WHERE task_type IN ('project','subtask') LIMIT 10;"

# 5. Run full test suite
uv run pytest services/ltt-core/tests/ -v
```

---

## Notes

- All five columns are nullable or have server defaults — existing data is unaffected.
- `tutor_config` is stored as JSONB, not as individual columns, because the structure may evolve (new fields like `language`, `difficulty_adaptation`).
- `subtask_type` only matters semantically on subtask-type tasks, but the column exists on all rows for simplicity. Non-subtask rows will have the default `"exercise"` (harmless).
- The `project_slug` partial unique index only constrains rows where `task_type = 'project'` — other task types can have `NULL` slugs.
