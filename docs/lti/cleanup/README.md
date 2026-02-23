# LTI Cleanup: Code to Remove or Lock Down

> Every file listed here exists outside the LTI access path. This is the definitive list of standalone-mode artifacts, unauthenticated endpoints, and dev scaffolding that must be addressed before production.

---

## Priority Legend

- **P0 — Security**: Unauthenticated access to learner data or grade manipulation
- **P1 — Dead code**: Standalone-mode UI that bypasses LTI entirely
- **P2 — Hardening**: Dev conveniences that should be removed or gated

---

## P0 — Security: Unauthenticated API Endpoints

### Problem

Every `/api/v1/*` endpoint accepts a raw `learner_id` query/body parameter with no authentication. Anyone with the API URL can impersonate any learner, view their progress, submit work on their behalf, and trigger grade passback.

### Files

| File | Lines | Endpoint | Issue |
|------|-------|----------|-------|
| `services/api-server/src/api/frontend_routes.py` | 27-35 | `ensure_learner_exists()` | Auto-creates learner records for any `learner_id` string — no LTI validation |
| `services/api-server/src/api/frontend_routes.py` | ~195 | `GET /api/v1/project/{id}/tree` | Accepts any `learner_id` query param |
| `services/api-server/src/api/frontend_routes.py` | ~343 | `GET /api/v1/task/{id}` | Accepts any `learner_id` query param |
| `services/api-server/src/api/frontend_routes.py` | ~426 | `GET /api/v1/project/{id}/ready` | Accepts any `learner_id` query param |
| `services/api-server/src/api/frontend_routes.py` | ~478 | `POST /api/v1/task/{id}/start` | Accepts any `learner_id` in body |
| `services/api-server/src/api/frontend_routes.py` | ~532 | `POST /api/v1/task/{id}/submit` | Accepts any `learner_id` in body |
| `services/api-server/src/api/frontend_routes.py` | — | `GET /api/v1/projects` | Lists all projects, no auth |
| `services/api-server/src/api/frontend_routes.py` | — | `GET /api/v1/project/{id}/database` | Returns SQL schema, no auth |
| `services/api-server/src/api/routes.py` | ~185 | `POST /api/v1/chat` | Accepts any `learner_id` in body |
| `services/api-server/src/api/routes.py` | ~253 | `POST /api/v1/chat/stream` | Accepts any `learner_id` in body |
| `services/api-server/src/api/routes.py` | ~318 | `POST /api/v1/session` | Accepts any `learner_id` in body |

### Fix

Add LTI validation middleware that:
1. Requires `X-LTI-Launch-Id` header on all `/api/v1/*` endpoints
2. Resolves `launch_id` → `learner_id` from Redis/DB (using `resolve_launch()` from `middleware.py`)
3. Ignores the `learner_id` from the request body/params — uses the one from the launch
4. Rejects requests without a valid launch

```python
# Proposed middleware in services/api-server/src/api/app.py
@app.middleware("http")
async def lti_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/"):
        launch_id = request.headers.get("x-lti-launch-id")
        if not launch_id:
            return JSONResponse(status_code=401, content={"detail": "LTI session required"})
        ctx = resolve_launch(launch_id, get_launch_data_storage())
        if not ctx:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired LTI session"})
        request.state.lti_context = ctx
    return await call_next(request)
```

Then update each endpoint to read `request.state.lti_context.learner_id` instead of the request param.

### Also remove

- `ensure_learner_exists()` function — learners should only be created via `get_or_create_lti_learner()` during `/lti/launch`

---

## P0 — Security: Debug Endpoints

### Problem

`/lti/debug/*` endpoints expose full JWT claims (PII), Redis internals, and allow test grade injection. They are gated only by the `DEBUG` env var, which is a deployment mistake waiting to happen.

### Files

| File | Lines | Endpoint | Exposes |
|------|-------|----------|---------|
| `services/api-server/src/api/lti/routes.py` | 289-307 | `GET /lti/debug/context` | Full launch JWT: sub, iss, email, name, roles, AGS config |
| `services/api-server/src/api/lti/routes.py` | 310-386 | `GET /lti/debug/health` | Redis status, DB status, platform config, key count |
| `services/api-server/src/api/lti/routes.py` | 389-428 | `POST /lti/debug/grade-test` | Sends arbitrary grades to the LMS gradebook |

### Fix

**Option A (recommended)**: Delete these endpoints entirely. Use server-side logging and monitoring instead.

**Option B**: Move behind proper authentication (e.g., instructor role check from LTI context + API key).

---

## P1 — Dead Code: Standalone Frontend Pages

### Problem

These pages allow anyone to access the system without going through LTI. They include a project picker, learner ID generator, and direct workspace access with arbitrary query params.

### Files to Remove

| File | Route | What it does |
|------|-------|--------------|
| `apps/web/src/app/page.tsx` | `/` | Home page with project selector + learner ID input. Links directly to `/workspace/:projectId` with arbitrary `learnerId` param. |
| `apps/web/src/app/project/[projectId]/page.tsx` | `/project/:projectId` | Project overview page. Falls back to `"learner-dev-001"` if no `learnerId` param. |
| `apps/web/src/app/debug/page.tsx` | `/debug` | LTI debug introspection page. Shows full launch data, health checks, grade test UI. |

### Fix

- Delete `apps/web/src/app/page.tsx` (or replace with a redirect to the LMS)
- Delete `apps/web/src/app/project/[projectId]/page.tsx`
- Delete `apps/web/src/app/debug/page.tsx`
- The only valid entry is `apps/web/src/app/workspace/[projectId]/page.tsx` via LTI redirect

---

## P1 — Dead Code: Standalone Components

### Files to Remove

| File | What it does |
|------|--------------|
| `apps/web/src/components/shared/ProjectSelector.tsx` | Dropdown to select from all projects. Calls `api.getProjects()`. Used by home page. |
| `apps/web/src/components/shared/LearnerIdInput.tsx` | Floating input to edit/generate learner IDs. Used by home page. Includes `useLearnerIdState()` hook. |
| `apps/web/src/components/shared/DebugButton.tsx` | Floating button linking to `/debug` page. Conditionally rendered in `layout.tsx`. |

### Also update

- `apps/web/src/app/layout.tsx` line 33: Remove `{process.env.NEXT_PUBLIC_DEBUG === "true" && <DebugButton />}`
- Remove the `DebugButton` import on line 5

---

## P1 — Dead Code: Cookie-Based Learner Management

### Problem

`learner.ts` contains a full cookie-based learner ID system (generate, store, retrieve). In LTI mode, the learner comes from the platform JWT. The cookie path exists only for standalone dev and should be removed.

### File

`apps/web/src/lib/learner.ts`

### What to keep

```typescript
// Only this function, simplified:
export function getLearnerId(): string | null {
  const lti = getLTIContext();
  if (lti?.isLTI && lti.learnerId) return lti.learnerId;
  return null;
}
```

### What to remove

- `generateLearnerId()` — random ID generation
- `setLearnerId()` — cookie storage
- `getLearnerId()` (cookie version) — reading from `document.cookie`
- `isValidLearnerId()` — regex validation (standalone format)
- `LEARNER_ID_COOKIE` constant
- `COOKIE_MAX_AGE` constant

---

## P2 — Hardening: Workspace Page Fallbacks

### Problem

The workspace page (`apps/web/src/app/workspace/[projectId]/page.tsx`) has a fallback chain that allows access without LTI:

```typescript
const learnerId = searchParams.get("learnerId")
  ?? ltiCtx?.learnerId
  ?? "learner-dev-001";  // ← This
```

### Fix

Remove the fallback chain. If no LTI context exists, show an error or redirect to the LMS:

```typescript
const ltiCtx = parseLTIContext(searchParams) ?? getLTIContext();
if (!ltiCtx?.isLTI) {
  return <div>This application is only accessible via your LMS.</div>;
}
const learnerId = ltiCtx.learnerId;
```

---

## P2 — Hardening: API fetch calls without LTI headers

### Problem

Some API calls in `apps/web/src/lib/api.ts` use plain `fetch()` instead of `lttFetch()`, meaning they don't send the `X-LTI-Launch-Id` header:

| Function | Line | Uses |
|----------|------|------|
| `getProjectTree()` | 53 | `fetch()` — no LTI header |
| `getTaskDetails()` | 65 | `fetch()` — no LTI header |
| `getReadyTasks()` | 77 | `fetch()` — no LTI header |
| `getDatabaseSchema()` | 159 | `fetch()` — no LTI header |

### Fix

Replace all `fetch()` calls with `lttFetch()`. Once the LTI auth middleware is in place (P0 fix above), these calls will fail without the header.

---

## P2 — Hardening: `/health` Endpoint

### Problem

`GET /health` returns `{"status": "healthy", "lti_enabled": true/false}`, exposing whether LTI is configured.

### Fix

Return only `{"status": "healthy"}`. Remove `lti_enabled` field.

---

## P2 — Hardening: `/lti/jwks` Endpoint

No action needed. This endpoint is intentionally unauthenticated — the platform must be able to fetch the tool's public keys.

---

## P2 — Hardening: CORS and CSP

### Current state

```python
# app.py
allow_origins=["*"]  # Wide open
```

```python
# CSP middleware
"frame-ancestors *"  # Allows embedding from any origin
```

### Fix

```python
allow_origins=[
    "https://imbizo.alx-ai-tools.com",
    os.getenv("LTT_FRONTEND_URL", "http://localhost:3000"),
]

# CSP
f"frame-ancestors https://imbizo.alx-ai-tools.com 'self'"
```

---

## Summary: Cleanup Order

1. **P0**: Add LTI auth middleware to `/api/v1/*` endpoints
2. **P0**: Remove or gate debug endpoints
3. **P1**: Delete standalone pages (`/`, `/project/*`, `/debug`)
4. **P1**: Delete standalone components (`ProjectSelector`, `LearnerIdInput`, `DebugButton`)
5. **P1**: Simplify `learner.ts` to LTI-only
6. **P2**: Remove workspace fallbacks
7. **P2**: Replace all `fetch()` with `lttFetch()` in `api.ts`
8. **P2**: Tighten CORS and CSP
9. **P2**: Clean up `/health` response

After this cleanup, the only way into the system is through an LTI launch from Open edX.
