# Phase Document Template

Use this structure for each `NN-short-name.md` phase document.

---

```markdown
# Phase NN: Title

> One-line goal.

**Status**: Not started
**Depends on**: [Phase NN or "None"]
**Unblocks**: [Phase NN or "Nothing"]

---

## Current State

What exists today. Include file paths with line numbers so the implementer can jump straight to the relevant code.

```
path/to/file.py:42 — current behavior description
path/to/model.py:18 — field exists / doesn't exist
```

## Changes

Group by layer. Each change should be specific enough to implement without re-reading the overview.

### Model Changes

| Field | Type | Default | Where | Notes |
|-------|------|---------|-------|-------|
| `field_name` | `VARCHAR(20)` | `'default'` | `TaskBase`, `TaskCreate`, `TaskModel` | New column |

### Migration

```sql
-- Alembic migration description
ALTER TABLE table_name ADD COLUMN field_name TYPE DEFAULT value;
```

### Service Changes

| File | Function | Change |
|------|----------|--------|
| `path/to/service.py` | `function_name()` | Pass `field=data.get("field")` to constructor |

### API Changes (if applicable)

| Method | Path | Change |
|--------|------|--------|
| `POST` | `/api/v1/endpoint` | Add `field` to response body |

### Frontend Changes (if applicable)

| File | Change |
|------|--------|
| `apps/web/src/path/to/component.tsx` | Read new field from API response |

## File Map

Every file that needs changes for this phase.

| File | Change | Lines |
|------|--------|-------|
| `path/to/model.py` | Add `field` to Pydantic model | ~18-25 |
| `path/to/service.py` | Pass `field` through | ~124 |
| `path/to/migration.py` | New migration file | New |
| `path/to/test.py` | Add/update test cases | ~50-80 |

## Test Plan

### New Tests

- `test_field_is_stored_on_ingest` — Verify field survives ingest round-trip
- `test_field_defaults_when_missing` — Verify default value when JSON omits field

### Updated Tests

- `test_existing_behavior` — Add assertion for new field

### Run

```bash
uv run pytest path/to/tests/ -v -k "test_name"
```

## Verification

Commands to confirm the phase works end-to-end.

```bash
# 1. Run migration
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head

# 2. Ingest test project
python -m ltt.cli.main ingest project content/projects/test.json --dry-run

# 3. Run tests
uv run pytest path/to/tests/ -v

# 4. Verify in DB (optional)
docker exec -it ltt-postgres psql -U ltt_user -d ltt_dev -c "SELECT field FROM table LIMIT 1;"
```

## Notes

Any caveats, open questions, or things the implementer should watch out for.
```
