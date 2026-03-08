# Phase 01: Fix Ingest Drops

> Pass through fields that already exist on TaskCreate/TaskModel but are currently ignored by ingest.py.

**Status**: Done
**Depends on**: None
**Unblocks**: Phase 02, Phase 07

---

## Current State

The ingestion pipeline silently drops fields that the Pydantic schema accepts AND the database already has columns for:

```
project.json ──→ ProjectSchema ──→ ingest.py ──→ TaskCreate ──→ TaskModel ──→ DB
     ✅                ✅              ❌            ✅             ✅          ✅
  (has fields)    (validates)     (ignores)    (has fields)   (has columns)  (ready)
```

### Fields dropped today

| Field | JSON level | On TaskBase? | On TaskModel (DB)? | Passed by ingest.py? |
|-------|-----------|-------------|-------------------|---------------------|
| `estimated_minutes` | all levels | Yes (line 61) | Yes (line 203) | **No** — ignored at project, epic, task, subtask |
| `priority` | epic | Yes (line 59) | Yes (line 200) | **No** — epics hardcode default; tasks/subtasks pass it |
| `version` | project | No (not on TaskCreate) | Yes (line 217, default `1`) | **No** |
| `version_tag` | project | No (not on TaskCreate) | Yes (line 218) | **No** |

### What already works

- `title`, `description`, `acceptance_criteria`, `content` — all passed through
- `tutor_guidance` — passed for tasks/subtasks (not epics, which is correct per schema)
- `narrative_context` — passed at project level
- `workspace_type`, `tutor_persona` — passed at project level
- `learning_objectives` — attached at all levels via `attach_objective()`
- `dependencies` — resolved by title at all levels
- `priority` — passed for tasks/subtasks only
- `requires_submission` — passed at all levels

---

## Changes

### Service Changes

| File | Function | Line | Change |
|------|----------|------|--------|
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_project_file()` | ~124 | Add `estimated_minutes=data.get("estimated_minutes")` to TaskCreate |
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_epic()` | ~201 | Add `estimated_minutes=data.get("estimated_minutes")` to TaskCreate |
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_epic()` | ~201 | Add `priority=data.get("priority", 2)` to TaskCreate |
| `services/ltt-core/src/ltt/services/ingest.py` | `ingest_task()` | ~326 | Add `estimated_minutes=data.get("estimated_minutes")` to TaskCreate |

### Model Changes (version/version_tag passthrough)

`version` and `version_tag` exist on `TaskModel` (DB columns) and on the `Task` response model (line 138–139), but NOT on `TaskCreate`. To pass them through during ingest:

| Field | Type | Default | Add To | Notes |
|-------|------|---------|--------|-------|
| `version` | `int` | `1` | `TaskCreate` (after `TaskBase`) | Only meaningful at project level |
| `version_tag` | `str \| None` | `None` | `TaskCreate` (after `TaskBase`) | Only meaningful at project level |

Then update `ingest_project_file()` (~line 124):
```python
TaskCreate(
    ...existing fields...,
    estimated_minutes=data.get("estimated_minutes"),
    version=data.get("version", 1),
    version_tag=data.get("version_tag"),
)
```

**No migration needed** — `version` (line 217) and `version_tag` (line 218) already exist as DB columns.

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/models/task.py` | Add `version`, `version_tag` to `TaskCreate` | ~102–112 |
| `services/ltt-core/src/ltt/services/ingest.py` | Add `estimated_minutes` to project-level TaskCreate | ~122–134 |
| `services/ltt-core/src/ltt/services/ingest.py` | Add `estimated_minutes`, `priority` to epic-level TaskCreate | ~200–212 |
| `services/ltt-core/src/ltt/services/ingest.py` | Add `estimated_minutes` to task/subtask-level TaskCreate | ~326–340 |
| `services/ltt-core/src/ltt/services/ingest.py` | Add `version`, `version_tag` to project-level TaskCreate | ~122–134 |
| `services/ltt-core/tests/services/test_ingest.py` | Add/update tests | New test functions |

---

## Test Plan

### New Tests

- `test_ingest_estimated_minutes_at_all_levels` — Ingest a project with `estimated_minutes` at project, epic, task, and subtask level. Verify all four values are stored in DB.
- `test_ingest_epic_priority` — Ingest a project with `priority: 0` on an epic. Verify the epic's TaskModel has `priority=0` (not the default `2`).
- `test_ingest_version_and_version_tag` — Ingest a project with `version: 2` and `version_tag: "v2-beta"`. Verify both values on the project's TaskModel.
- `test_ingest_defaults_when_fields_omitted` — Ingest a project without optional fields. Verify `estimated_minutes=None`, `version=1`, `version_tag=None`, epic `priority=2`.

### Updated Tests

- `test_ingest_simple_project` (line 20) — Add assertion that `estimated_minutes` is `None` when omitted.

### Run

```bash
uv run pytest services/ltt-core/tests/services/test_ingest.py -v
```

---

## Verification

```bash
# 1. Run tests
uv run pytest services/ltt-core/tests/services/test_ingest.py -v -k "estimated_minutes or epic_priority or version"

# 2. Ingest a test project with these fields
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json --dry-run

# 3. Full ingest and check DB
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "SELECT id, task_type, estimated_minutes, priority, version, version_tag FROM tasks WHERE task_type IN ('project','epic') LIMIT 10;"
```

---

## Notes

- This phase has **zero schema/migration changes** — every field already exists in the DB.
- The `version` field on TaskModel defaults to `1` at the DB level, so existing data is unaffected.
- `estimated_minutes` should stay `None` when omitted (not default to `0`) — it's an optional hint, not a requirement.
