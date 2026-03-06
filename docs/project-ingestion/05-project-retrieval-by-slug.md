# Phase 05: Project Retrieval by Slug

> Fetch a project by its stable `project_id` slug instead of the internal `proj-XXXX` ID.

**Status**: Not started
**Depends on**: Phase 02 (`project_slug` column + index)
**Unblocks**: Phase 06

---

## Current State

Projects are only retrievable by their auto-generated internal ID (`proj-a1b2`):

- `task_service.py` has `get_task(session, task_id)` — looks up by primary key `id`
- No `get_project_by_slug()` function exists anywhere
- The LTI launch flow uses `project_id` from the custom parameter — currently assumed to be the internal ID
- API endpoints: `GET /api/v1/projects` lists all, `GET /api/v1/project/{project_id}/tree` fetches by internal ID

After Phase 02, the `project_slug` column exists and is populated during ingest. This phase adds the retrieval layer.

---

## Changes

### New Service Function

Add to `services/ltt-core/src/ltt/services/task_service.py`:

```python
async def get_project_by_slug(
    session: AsyncSession,
    slug: str,
    version: int | None = None,
) -> TaskModel | None:
    """Get a project by its stable slug. Returns latest version if version not specified."""
    query = select(TaskModel).where(
        TaskModel.project_slug == slug,
        TaskModel.task_type == "project",
    )
    if version is not None:
        query = query.where(TaskModel.version == version)
    else:
        query = query.order_by(TaskModel.version.desc())
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none()
```

### New API Endpoint

Add to `services/api-server/src/api/frontend_routes.py`:

```
GET /api/v1/projects/{slug}           → latest version
GET /api/v1/projects/{slug}?version=2 → specific version
```

Response:
```json
{
  "project_id": "maji-ndogo-part1",
  "internal_id": "proj-9b46",
  "version": 1,
  "title": "Maji Ndogo Water Crisis - Part 1",
  "description": "...",
  "workspace_type": "sql"
}
```

### Update LTI Launch Flow

`services/api-server/src/api/lti/routes.py` — In the launch handler, resolve the `project_id` custom parameter:

```python
# Current: assumes project_id is internal ID
project_id = custom_params.get("project_id")

# New: try slug lookup first, fall back to internal ID
project = await get_project_by_slug(session, project_id)
if project:
    internal_project_id = project.id
else:
    # Fall back — might be an internal ID directly
    internal_project_id = project_id
```

This maintains backward compatibility while supporting the new slug-based lookup.

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/services/task_service.py` | Add `get_project_by_slug()` | New function |
| `services/api-server/src/api/frontend_routes.py` | Add `GET /api/v1/projects/{slug}` endpoint | New route |
| `services/api-server/src/api/lti/routes.py` | Resolve slug in LTI launch | Launch handler |
| `services/ltt-core/tests/services/test_task_service.py` | Test slug lookup | New tests |
| `services/api-server/tests/` | Test slug endpoint + LTI resolution | New tests |

---

## Test Plan

### New Tests (ltt-core)

- `test_get_project_by_slug_found` — Create project with `project_slug="test-slug"`, retrieve by slug, verify match.
- `test_get_project_by_slug_not_found` — Query non-existent slug, verify `None` returned.
- `test_get_project_by_slug_latest_version` — Create two projects with same slug, versions 1 and 2. Verify unversioned query returns version 2.
- `test_get_project_by_slug_specific_version` — Same setup, query with `version=1`, verify version 1 returned.

### New Tests (api-server)

- `test_get_project_by_slug_endpoint` — `GET /api/v1/projects/test-slug` returns 200 with correct data.
- `test_get_project_by_slug_404` — `GET /api/v1/projects/nonexistent` returns 404.
- `test_lti_launch_resolves_slug` — LTI launch with `project_id=test-slug` custom parameter resolves to internal ID.
- `test_lti_launch_fallback_to_internal_id` — LTI launch with `project_id=proj-a1b2` still works (backward compat).

### Run

```bash
uv run pytest services/ltt-core/tests/services/test_task_service.py -v -k "slug"
uv run --package api-server pytest services/api-server/tests/ -v -k "slug"
```

---

## Verification

```bash
# 1. Ingest a project (with project_slug from Phase 02)
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json

# 2. Query by slug
curl http://localhost:8000/api/v1/projects/maji-ndogo-part1 | jq .

# 3. Verify LTI launch with slug
# (Configure Open edX LTI custom parameter: project_id=maji-ndogo-part1)
# Launch from Open edX and verify workspace loads

# 4. Run tests
uv run pytest services/ltt-core/tests/ services/api-server/tests/ -v -k "slug"
```

---

## Notes

- The slug lookup is `O(1)` due to the partial unique index on `(project_slug, version)` from Phase 02.
- The `GET /api/v1/projects/{slug}` endpoint is separate from the existing `GET /api/v1/projects` (list all). No collision — the list endpoint has no path parameter.
- The LTI launch fallback ensures existing deployments (using internal IDs in Open edX config) continue to work.
