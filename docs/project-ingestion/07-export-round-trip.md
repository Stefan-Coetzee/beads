# Phase 07: Export Round-Trip

> Export includes all fields so that export → ingest is lossless.

**Status**: Done
**Depends on**: Phase 01 (all fields passed through), Phase 02 (new columns), Phase 04 (grade fields)
**Unblocks**: Nothing (final phase)

---

## Current State

`export.py` (line 17) misses many fields that are now stored in the DB:

### `export_project()` — line 17

Currently includes: `title`, `description`, `learning_objectives`, `content`, `narrative_context` (conditional), `epics`.

**Missing from project export**:
- `project_id` (from `project_slug`)
- `version`
- `version_tag`
- `workspace_type`
- `tutor_persona`
- `tutor_config` (Phase 02)
- `narrative` (Phase 02)
- `estimated_minutes`
- `requires_submission`

### `export_task_tree()` — line 69

Currently includes: `title`, `description`, `acceptance_criteria`, `learning_objectives`, `priority`, `content`, `tutor_guidance` (conditional), `dependencies`.

**Missing from task/subtask export**:
- `estimated_minutes`
- `requires_submission`
- `subtask_type` (Phase 02, subtask level)
- `max_grade` (Phase 02, task level)

---

## Changes

### Update `export_project()`

Add all missing project-level fields:

```python
project_data = {
    "project_id": project.project_slug,     # Phase 02 — stable slug
    "version": project.version,              # Phase 01
    "version_tag": project.version_tag,      # Phase 01 (if not None)
    "title": project.title,
    "description": project.description,
    "workspace_type": project.workspace_type, # existing column
    "narrative": project.narrative,           # Phase 02
    "narrative_context": project.narrative_context,  # existing
    "tutor_persona": project.tutor_persona,  # existing
    "tutor_config": project.tutor_config,    # Phase 02
    "estimated_minutes": project.estimated_minutes,  # Phase 01
    "requires_submission": project.requires_submission,  # existing
    "learning_objectives": [...],
    "content": project.content,
    "epics": [...],
}
```

Omit keys with `None` values (match current pattern for `narrative_context`).

### Update `export_task_tree()`

Add missing fields at task/subtask level:

```python
task_data = {
    "title": task.title,
    "description": task.description,
    "acceptance_criteria": task.acceptance_criteria,
    "estimated_minutes": task.estimated_minutes,   # Phase 01
    "priority": task.priority,
    "max_grade": task.max_grade,                   # Phase 02 (tasks)
    "subtask_type": task.subtask_type,             # Phase 02 (subtasks)
    "requires_submission": task.requires_submission,
    "content": task.content,
    "tutor_guidance": task.tutor_guidance,
    "learning_objectives": [...],
    "dependencies": [...],
    "subtasks": [...] or "tasks": [...],
}
```

Only include `subtask_type` when `task_type == "subtask"`. Only include `max_grade` when `task_type == "task"`.

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/services/export.py` | Add missing fields to `export_project()` | ~17–66 |
| `services/ltt-core/src/ltt/services/export.py` | Add missing fields to `export_task_tree()` | ~69–120 |
| `services/ltt-core/tests/services/test_export.py` | Verify all fields in export + round-trip | ~220+ |

---

## Test Plan

### New Tests

- `test_export_includes_project_slug` — Ingest project with `project_id` slug, export, verify `project_id` key in output.
- `test_export_includes_version` — Verify `version` and `version_tag` in export.
- `test_export_includes_estimated_minutes` — Set `estimated_minutes` at all levels, export, verify all present.
- `test_export_includes_subtask_type` — Ingest subtask with `subtask_type: "conversational"`, export, verify field present.
- `test_export_includes_max_grade` — Ingest task with `max_grade: 10`, export, verify present.
- `test_export_includes_workspace_type` — Verify `workspace_type` in project export.
- `test_export_includes_tutor_config` — Verify `tutor_config` in project export.
- `test_export_includes_narrative` — Verify `narrative` boolean in project export.
- `test_export_omits_none_values` — Fields that are `None` should be omitted from output (not `"field": null`).

### Updated Tests

- `test_roundtrip_export_import` (line 220) — Expand to verify ALL new fields survive the round-trip (export → import → export → compare).

### Run

```bash
uv run pytest services/ltt-core/tests/services/test_export.py -v
```

---

## Verification

```bash
# 1. Ingest a full project with all fields populated
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json

# 2. Export
python -m ltt.cli.main project export $(project_id) --output /tmp/exported.json --format json

# 3. Inspect exported JSON for all fields
cat /tmp/exported.json | python -m json.tool | head -30
# Verify: project_id, version, workspace_type, narrative, tutor_config, estimated_minutes

# 4. Round-trip: re-ingest the export (bump version first)
# Edit /tmp/exported.json: change version to 2
python -m ltt.cli.main ingest project /tmp/exported.json

# 5. Export again and diff
python -m ltt.cli.main project export $(new_project_id) --output /tmp/exported_v2.json --format json
diff <(python -m json.tool /tmp/exported.json) <(python -m json.tool /tmp/exported_v2.json)
# Expected: only version number differs

# 6. Run tests
uv run pytest services/ltt-core/tests/services/test_export.py -v
```

---

## Notes

- The round-trip test is the definitive quality gate — if `export → ingest → export` produces identical JSON (modulo internal IDs and version), the pipeline is lossless.
- `project_id` in the export JSON maps to `project_slug` in the DB. The export uses `project_id` to match the input format.
- JSONL format (`--format jsonl`) should also include these fields — verify `test_export_jsonl_format` covers them.
