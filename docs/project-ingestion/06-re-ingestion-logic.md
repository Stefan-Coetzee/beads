# Phase 06: Re-Ingestion Logic

> Ingesting a project with an existing slug creates a new version instead of a duplicate.

**Status**: Done
**Depends on**: Phase 02 (`project_slug` + `version`), Phase 05 (`get_project_by_slug()`)
**Unblocks**: Phase 07

---

## Current State

`ingest_project_file()` in `ingest.py` (line 64) creates a new project every time it's called. There is no duplicate detection:

- No check for existing `project_slug`
- No version comparison
- Re-ingesting the same JSON creates a second project with a different internal ID (`proj-XXXX`)
- Learner progress on the old version is orphaned (still points to old task IDs)

After Phases 02 and 05:
- `project_slug` is stored on the project task
- `version` is stored (defaults to `1`)
- `get_project_by_slug(session, slug, version)` can look up existing projects

---

## Changes

### Update `ingest_project_file()`

Add duplicate detection at the start of `ingest_project_file()` (~line 80, before TaskCreate):

```python
# 1. Check for existing project with same slug
slug = data.get("project_id")  # author-defined slug
version = data.get("version", 1)

if slug:
    existing = await get_project_by_slug(session, slug, version)
    if existing:
        # Same slug + same version → reject
        raise ValueError(
            f"Project '{slug}' version {version} already exists "
            f"(internal ID: {existing.id}). "
            f"Bump the version number in your JSON to create a new version."
        )

    # Same slug + higher version → OK, create new version
    latest = await get_project_by_slug(session, slug)  # no version filter → latest
    if latest and version <= latest.version:
        raise ValueError(
            f"Project '{slug}' already has version {latest.version}. "
            f"New version must be higher (got {version})."
        )
```

### Behavior Matrix

| Scenario | Behavior |
|----------|----------|
| New slug | Create normally |
| Same slug, same version | **Reject** with descriptive error |
| Same slug, higher version | **Create new version** — old learners stay on old version |
| Same slug, lower version | **Reject** — versions must increase monotonically |
| No slug (`project_id` omitted) | Create normally (no duplicate detection) |

### Why not update-in-place?

If learners are mid-project and we swap the task tree under them, their progress references (task IDs) break. The `learner_task_progress` table links to specific task IDs. Creating a new version preserves existing progress while letting new learners start fresh.

**Not in this phase**: migrating learner progress between versions.

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/ltt-core/src/ltt/services/ingest.py` | Add duplicate detection in `ingest_project_file()` | ~80 (before TaskCreate) |
| `services/ltt-core/tests/services/test_ingest.py` | Test re-ingestion scenarios | New tests |

---

## Test Plan

### New Tests

- `test_reingest_same_slug_same_version_rejected` — Ingest project with `project_id: "test-proj", version: 1`. Ingest again with same slug and version. Verify `ValueError` raised with descriptive message.
- `test_reingest_same_slug_higher_version_creates_new` — Ingest v1, then ingest v2 of same slug. Verify two separate project tasks exist, each with correct version and different internal IDs.
- `test_reingest_same_slug_lower_version_rejected` — Ingest v2, then try v1. Verify `ValueError`.
- `test_reingest_no_slug_allows_duplicates` — Ingest project without `project_id` twice. Verify both created (no duplicate detection without slug).
- `test_reingest_preserves_old_learner_progress` — Ingest v1, create learner progress on v1 tasks, ingest v2. Verify v1 progress is untouched.
- `test_dry_run_reingest_reports_conflict` — Dry run on existing slug+version reports the conflict without DB changes.

### Run

```bash
uv run pytest services/ltt-core/tests/services/test_ingest.py -v -k "reingest"
```

---

## Verification

```bash
# 1. Ingest v1
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json

# 2. Try re-ingesting same version (should fail)
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json
# Expected: error message about duplicate slug+version

# 3. Modify JSON to version: 2, ingest again (should succeed)
# (Edit the JSON or use a copy)

# 4. Verify both versions exist
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "SELECT id, project_slug, version FROM tasks WHERE task_type = 'project';"

# 5. Run tests
uv run pytest services/ltt-core/tests/services/test_ingest.py -v -k "reingest"
```

---

## Notes

- The partial unique index on `(project_slug, version)` from Phase 02 provides a DB-level safety net, but we validate in code first for better error messages.
- Future enhancement: `--force` flag on CLI to update-in-place (destructive, with warnings).
- Future enhancement: version migration tool that maps old task IDs to new ones and migrates learner progress.
- The `version_tag` field (e.g., `"v2-beta"`) is informational — only `version` (integer) controls deduplication.
