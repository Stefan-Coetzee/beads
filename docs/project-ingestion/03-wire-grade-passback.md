# Phase 03: Wire Grade Passback into Submit Flow

> When a learner submits work and it passes validation, send grade to the LMS.

**Status**: Not started
**Depends on**: Phase 02 (project_slug for project identification)
**Unblocks**: Phase 04

---

## Current State

Grade passback infrastructure is **fully built but completely unwired**:

- `services/api-server/src/api/lti/grades.py` has `send_grade()` (line 23) and `maybe_send_grade()` (line 99) — both functional
- `maybe_send_grade()` is **never called** from any production code path
- `send_grade()` is only called from `maybe_send_grade()` and from a debug endpoint in `lti/routes.py` (line 447)
- The `submit()` tool in `ltt-core/tools/progress.py` (line 140) handles submission + validation + task closure but has **no grade passback hook**

### Why not in the tool?

The `submit()` tool lives in `ltt-core`, which has no Redis dependency. `maybe_send_grade()` needs Redis (for LTI launch data lookup). Keeping the boundary clean: ltt-core handles business logic, api-server handles LTI integration.

### Current submit flow

```
submit() in ltt-core/tools/progress.py
  ├── create_submission()           line 178
  ├── validate_submission()         line 183
  ├── if validation.passed:
  │   ├── close_task()              line 194
  │   ├── try_auto_close_ancestors() line 201
  │   └── fetch ready tasks         lines 222-248
  └── return SubmitOutput
```

### Where submissions happen today

The `POST /api/v1/task/{task_id}/submit` route in `frontend_routes.py` is **commented out** (lines 525–564). All submissions currently go through the agent chat flow (the agent calls the `submit()` tool).

The agent chat route is in `services/api-server/src/api/routes.py` — it invokes the LangGraph agent which may call the `submit()` tool internally.

---

## Changes

### Option 3: Grade passback at the API route layer (recommended)

After the agent completes a turn that resulted in a submission, check whether any tasks were closed and send grade if so.

### API Changes

| File | Location | Change |
|------|----------|--------|
| `services/api-server/src/api/routes.py` | After agent turn completes | Check for newly closed tasks, call `maybe_send_grade()` |

**Implementation approach**: After the agent's response is generated, compare task statuses before/after. If any task transitioned to `closed`, compute project progress and call `maybe_send_grade()`.

Alternatively, add a lightweight **callback** that the agent tool framework invokes after `submit()` succeeds:

```python
# In the API route that handles agent chat:
async def on_task_closed(task_id: str, learner_id: str, project_id: str, session: AsyncSession):
    """Called when a task closes during an agent turn."""
    progress = await get_progress(session, learner_id, project_id)
    maybe_send_grade(
        learner_id=learner_id,
        project_id=project_id,
        completed=progress.completed_tasks,
        total=progress.total_tasks,
        storage=get_launch_data_storage(),
    )
```

### Re-enable the Submit Endpoint (optional, parallel)

If `POST /api/v1/task/{task_id}/submit` is re-enabled (currently commented out at `frontend_routes.py` lines 525–564), add grade passback there too:

```python
@frontend_router.post("/api/v1/task/{task_id}/submit")
async def submit_work(task_id: str, ...):
    result = await submit(SubmitInput(...), learner_id, session)
    if result.success and result.task_status == "closed":
        progress = await get_progress(session, learner_id, project_id)
        maybe_send_grade(learner_id, project_id, progress.completed_tasks, progress.total_tasks, storage)
    return result
```

---

## File Map

| File | Change | Lines |
|------|--------|-------|
| `services/api-server/src/api/routes.py` | Add grade passback after agent turn | After agent invoke |
| `services/api-server/src/api/frontend_routes.py` | Add grade passback to submit endpoint (if re-enabled) | ~525–564 |
| `services/api-server/tests/` | Test grade passback wiring | New test file |

---

## Test Plan

### New Tests

- `test_grade_sent_after_successful_submission` — Mock `maybe_send_grade()`, submit work that passes validation, verify `maybe_send_grade()` called with correct `completed`/`total` args.
- `test_grade_not_sent_on_failed_validation` — Submit work that fails validation. Verify `maybe_send_grade()` NOT called.
- `test_grade_not_sent_without_redis` — When `storage=None` (no Redis), verify `maybe_send_grade()` returns `False` gracefully.
- `test_grade_includes_ancestor_closures` — Submit work that closes a subtask AND auto-closes the parent task. Verify grade reflects all closures.

### Run

```bash
uv run --package api-server pytest services/api-server/tests/ -v -k "grade"
```

---

## Verification

```bash
# 1. Start full stack with Redis
docker compose up -d postgres redis
LTT_REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 --app-dir services/api-server/src

# 2. Create a test launch session (via dev login)
curl -X POST http://localhost:8000/lti/dev/login -H "Content-Type: application/json" -d '{"learner_id": "test-learner", "project_id": "proj-xxx"}'

# 3. Submit work through the agent chat
# (Use the frontend or curl the chat endpoint)

# 4. Check Redis for grade passback attempt
# (Logs should show maybe_send_grade call — will return False without real AGS endpoint)

# 5. Run tests
uv run --package api-server pytest services/api-server/tests/ -v -k "grade"
```

---

## Notes

- This phase uses **binary grading only** — `completed/total` tasks as score. Phase 04 adds numeric grade storage.
- `maybe_send_grade()` is synchronous (not async) — it makes HTTP calls to the LMS. Consider wrapping in `asyncio.to_thread()` to avoid blocking the event loop.
- If there's no active LTI launch (e.g., dev mode without Redis), `maybe_send_grade()` returns `False` silently — no error.
- The debug endpoint at `lti/routes.py:447` already tests `send_grade()` with hardcoded values — useful for verifying AGS connectivity.
