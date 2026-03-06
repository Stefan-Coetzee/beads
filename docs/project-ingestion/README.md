# Project Ingestion — Implementation Plan

> What needs to happen to make ingestion, retrieval, and grading work end-to-end.

**Status**: Schema and docs designed. Code not yet updated.

---

## The Gap

The project JSON schema (`ProjectSchema`) and docs are ahead of the code. Fields exist in JSON and in the Pydantic validation model but are silently dropped during ingestion.

```
project.json ──→ ProjectSchema ──→ ingest.py ──→ TaskCreate ──→ TaskModel ──→ DB
     ✅                ✅              ❌            ❌             ⚠️          ⚠️
  (has fields)    (validates)     (ignores)    (missing fields) (some exist) (some exist)
```

### What the JSON has but ingest.py drops

| Field | JSON level | On TaskCreate? | On TaskModel/DB? | ingest.py passes it? |
|---|---|---|---|---|
| `project_id` (slug) | project | No | No | No |
| `version` | project | No | Yes (`version` column, always 1) | No |
| `version_tag` | project | No | Yes (`version_tag` column, always null) | No |
| `narrative` | project | No | No | No |
| `tutor_config` | project | No | No | No |
| `estimated_minutes` | all levels | Yes (on TaskBase) | Yes | No — silently dropped |
| `priority` | epic | Yes (on TaskBase) | Yes | No — epics hardcode default |
| `subtask_type` | subtask | No | No | No |
| `max_grade` | task | No | No | No |

### What works today

- `title`, `description`, `acceptance_criteria`, `content` — all passed through
- `tutor_guidance` — passed for tasks/subtasks (not epics, which is correct)
- `narrative_context` — passed at project level
- `workspace_type` — passed at project level
- `tutor_persona` — passed at project level (legacy, replaced by `tutor_config`)
- `learning_objectives` — attached at all levels
- `dependencies` — resolved by title at all levels
- `priority` — passed for tasks/subtasks only (not epics)
- `requires_submission` — passed at all levels

---

## Phase Summary

| Phase | Title | Status | Depends On | Unblocks |
|-------|-------|--------|------------|----------|
| [01](01-fix-ingest-drops.md) | Fix ingest drops | Not started | — | 02, 07 |
| [02](02-add-new-db-fields.md) | Add new DB fields | Not started | 01 | 03, 04, 05, 06, 07 |
| [03](03-wire-grade-passback.md) | Wire grade passback | Not started | 02 | 04 |
| [04](04-grade-storage.md) | Grade storage on validations | Not started | 02, 03 | 07 |
| [05](05-project-retrieval-by-slug.md) | Project retrieval by slug | Not started | 02 | 06 |
| [06](06-re-ingestion-logic.md) | Re-ingestion logic | Not started | 02, 05 | 07 |
| [07](07-export-round-trip.md) | Export round-trip | Not started | 01, 02, 04 | — |

### Dependency Graph

```
01 Fix ingest drops
 └──→ 02 Add new DB fields
       ├──→ 03 Wire grade passback ──→ 04 Grade storage ──┐
       ├──→ 05 Retrieval by slug ──→ 06 Re-ingestion ─────┤
       └───────────────────────────────────────────────────┴──→ 07 Export round-trip
```

### Implementation Order

```
Phase 01: Fix ingest drops                [foundation — no schema changes]
Phase 02: Add new DB fields               [schema — single Alembic migration]
Phase 03: Wire grade passback             [integration — connects existing AGS code]
Phase 04: Grade storage on validations    [schema — grade fields on validations table]
Phase 05: Project retrieval by slug       [API — new endpoint + LTI update]
Phase 06: Re-ingestion logic              [business logic — version deduplication]
Phase 07: Export round-trip               [completeness — lossless export ↔ ingest]
```

---

## Documents

### Phase docs

| Doc | Description |
|---|---|
| [01-fix-ingest-drops.md](01-fix-ingest-drops.md) | Pass through `estimated_minutes`, `priority` (epic), `version`, `version_tag` |
| [02-add-new-db-fields.md](02-add-new-db-fields.md) | Add `subtask_type`, `narrative`, `tutor_config`, `max_grade`, `project_slug` to DB |
| [03-wire-grade-passback.md](03-wire-grade-passback.md) | Call `maybe_send_grade()` after successful task submission |
| [04-grade-storage.md](04-grade-storage.md) | Add `grade`, `grader_type`, `feedback` to validations table |
| [05-project-retrieval-by-slug.md](05-project-retrieval-by-slug.md) | `get_project_by_slug()` service + API endpoint + LTI launch update |
| [06-re-ingestion-logic.md](06-re-ingestion-logic.md) | Duplicate detection + version increment on re-ingest |
| [07-export-round-trip.md](07-export-round-trip.md) | Include all fields in export for lossless round-trip |

### Companion docs

| Doc | Description |
|---|---|
| [grading.md](grading.md) | Grading requirements, strategies (LLM, rubric, test-based), and `max_grade` distribution |
| [rest-endpoint.md](rest-endpoint.md) | `POST /api/v1/projects/ingest` REST endpoint spec |

---

## Key Decisions

### Why `project_slug` not `project_id` in the DB?

The `project_id` column already exists on every task row — it stores the internal ID of the root project (e.g., `proj-a1b2`). The author-defined slug is a different concept. Using `project_slug` avoids ambiguity. In the JSON and API, the field is still called `project_id`.

### Why grade passback at the API layer, not in the tool?

The `submit()` tool lives in ltt-core, which has no Redis dependency. Grade passback needs Redis (for LTI launch data). Keeping the boundary clean: ltt-core handles business logic, api-server handles LTI integration.

### Why not update-in-place on re-ingestion?

If learners are mid-project and we swap the task tree under them, their progress references (task IDs) break. Safer to create a new version and let new learners start on the new version while existing learners finish the old one.

### Why a single migration for all Phase 02 columns?

All five columns are additive (nullable or with server defaults) and affect the same table. A single migration is simpler to reason about, review, and roll back than five separate ones.

---

## File Map

Every file that needs changes, grouped by phase.

### Phase 01 (ingest drops)
- `services/ltt-core/src/ltt/models/task.py` — add `version`, `version_tag` to TaskCreate
- `services/ltt-core/src/ltt/services/ingest.py` — pass through existing fields
- `services/ltt-core/tests/services/test_ingest.py` — verify fields stored

### Phase 02 (new DB fields)
- `services/ltt-core/src/ltt/models/task.py` — add fields to TaskBase, TaskCreate, TaskModel
- `services/ltt-core/src/ltt/db/migrations/versions/` — new Alembic migration
- `services/ltt-core/src/ltt/services/ingest.py` — pass new fields
- `services/ltt-core/tests/` — tests for new fields

### Phase 03 (grade passback)
- `services/api-server/src/api/routes.py` — call `maybe_send_grade()` after submit
- `services/api-server/tests/` — test grade passback wiring

### Phase 04 (grade storage)
- `services/ltt-core/src/ltt/models/validation.py` — add grade fields to Validation
- `services/ltt-core/src/ltt/db/migrations/versions/` — new Alembic migration
- `services/ltt-core/src/ltt/services/validation_service.py` — set grade on validation
- `services/ltt-core/tests/` — test grade storage

### Phase 05 (slug retrieval)
- `services/ltt-core/src/ltt/services/task_service.py` — `get_project_by_slug()`
- `services/api-server/src/api/frontend_routes.py` — new endpoint
- `services/api-server/src/api/lti/routes.py` — resolve slug in LTI launch
- `services/api-server/tests/` — test slug lookup

### Phase 06 (re-ingestion)
- `services/ltt-core/src/ltt/services/ingest.py` — duplicate detection + versioning
- `services/ltt-core/tests/services/test_ingest.py` — test re-ingestion scenarios

### Phase 07 (export)
- `services/ltt-core/src/ltt/services/export.py` — include all new fields
- `services/ltt-core/tests/services/test_export.py` — test round-trip

---

## Reference Files

| What | Where |
|---|---|
| **JSON schema guide** | [docs/schema/project-ingestion.md](../schema/project-ingestion.md) |
| **Pydantic validation models** | [services/ltt-core/src/ltt/models/project_schema.py](../../services/ltt-core/src/ltt/models/project_schema.py) |
| **Ingestion code** | [services/ltt-core/src/ltt/services/ingest.py](../../services/ltt-core/src/ltt/services/ingest.py) |
| **Task models (Pydantic + SQLAlchemy)** | [services/ltt-core/src/ltt/models/task.py](../../services/ltt-core/src/ltt/models/task.py) |
| **Export code** | [services/ltt-core/src/ltt/services/export.py](../../services/ltt-core/src/ltt/services/export.py) |
| **Grade passback** | [services/api-server/src/api/lti/grades.py](../../services/api-server/src/api/lti/grades.py) |
| **Submit tool** | [services/ltt-core/src/ltt/tools/progress.py](../../services/ltt-core/src/ltt/tools/progress.py) |
| **Validation service** | [services/ltt-core/src/ltt/services/validation_service.py](../../services/ltt-core/src/ltt/services/validation_service.py) |
| **Validation models** | [services/ltt-core/src/ltt/models/validation.py](../../services/ltt-core/src/ltt/models/validation.py) |
| **API routes (frontend)** | [services/api-server/src/api/frontend_routes.py](../../services/api-server/src/api/frontend_routes.py) |
| **LTI routes** | [services/api-server/src/api/lti/routes.py](../../services/api-server/src/api/lti/routes.py) |
| **Task service** | [services/ltt-core/src/ltt/services/task_service.py](../../services/ltt-core/src/ltt/services/task_service.py) |
| **Multi-domain extensibility** | [docs/design/multi-domain-extensibility.md](../design/multi-domain-extensibility.md) |
| **Reference project (SQL)** | [content/projects/DA/MN_Part1/structured/water_analysis_project.json](../../content/projects/DA/MN_Part1/structured/water_analysis_project.json) |
| **Reference project (Python)** | [content/projects/PYTHON/fundamentals/structured/python_basics_project.json](../../content/projects/PYTHON/fundamentals/structured/python_basics_project.json) |
