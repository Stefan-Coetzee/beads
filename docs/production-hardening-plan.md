# Production Hardening: Security, Statelessness, Environment Config

> Plan for preparing LTT for EKS/ALB deployment with LTI-only access.

## Context

LTT needs to run on EKS with ALB (stateless, horizontally scaled) and serve learners exclusively via LTI 1.3 from Open edX. The current codebase has:
- Zero API authentication (learner_id is client-controlled)
- In-memory agent cache (not horizontally scalable)
- Scattered env var reads (no central config)
- Wide-open CORS/CSP
- 25 security items to address (P0-P3)

This plan adds auth middleware, a central settings module, a dev login flow, stateless agent architecture, and security hardening — while keeping existing tests passing and local dev ergonomic.

---

## Phase 1: Settings Module

**Why first**: Everything else reads config. One source of truth eliminates scattered `os.getenv()`.

- Create `services/api-server/src/api/settings.py` — Pydantic `BaseSettings` with `LTT_` env prefix
- `auth_enabled=False` by default — existing tests and local dev work unchanged
- Startup validation: if `env=prod`, assert `auth_enabled=True`, `cors_origins != ["*"]`, `redis_url` set
- LTI keys: detect PEM string (starts with `-----BEGIN`) vs file path — supports K8s secrets as env vars
- Refactor `database.py`, `app.py`, `lti/config.py` to use `get_settings()`
- Create `.env.example` files for local, dev, prod

## Phase 2: Auth Middleware (P0 Security)

**Design**: FastAPI dependency injection, not `BaseHTTPMiddleware` (which breaks SSE streaming).

- Create `services/api-server/src/api/auth.py` with `get_learner_context()` dependency
- `LearnerContext` dataclass: `learner_id`, `project_id`, `launch_id`, `is_instructor`, `source`
- Resolves from `X-LTI-Launch-Id` header → Redis `launch_info:{id}` lookup
- When `auth_enabled=False`: falls back to `dev_learner_id` from settings
- Wire into `frontend_routes.py` (6 endpoints) and `routes.py` (4 endpoints)
- Remove `learner_id` from `StartTaskRequest`, `SubmitWorkRequest`, `ChatRequest`, `SessionRequest`
- `project_id` strictly from launch context (one launch = one project, no body override)

## Phase 3: Dev Login Endpoint

**Why**: Local dev needs to work without Open edX. Same auth code path as production.

- Add `POST /lti/dev/login` — creates fake Redis-backed launch (24h TTL)
- Only available when `auth_enabled=False`
- Add `devLogin()` to frontend `lti.ts`
- Auto-login in workspace page when not in iframe and no LTI context
- Without Redis: `get_learner_context` returns dev fallback directly

## Phase 4: Frontend Auth Cleanup

- All `fetch()` calls → `lttFetch()` (attaches `X-LTI-Launch-Id` header)
- Remove `learnerId` parameter from API method signatures
- Tighten `postMessage` origin from `"*"` to platform URL
- Simplify `learner.ts` — no longer used for auth

## Phase 5: Stateless Agent Architecture

**Problem**: `AgentManager` caches agents in `Dict[str, AgentWrapper]` — not horizontally scalable.

**Solution**: Replace in-memory `MemorySaver` with `PostgresSaver` (same database). Agent objects recreated per request (cheap). Conversation state persists in PostgreSQL.

- Add `langgraph-checkpoint-postgres` dependency
- Delete `AgentManager` class, replace with per-request `create_agent()` + shared `AsyncPostgresSaver`
- Init checkpointer in FastAPI lifespan
- No changes to `agent-tutor/graph.py` — already accepts `checkpointer` param

## Phase 6: Security Hardening

### P0 — Critical (resolved by Phases 1-4)

| # | Item | Resolution |
|---|------|------------|
| 1 | No API auth | `get_learner_context` dependency |
| 2 | No authorization | learner_id from server-side session |
| 3 | Weak learner ID entropy | Cookie-based IDs no longer used for auth |
| 4 | CORS wildcard + credentials | `settings.cors_origins` — prod-restricted |
| 5 | Frontend trusts URL params | Dev login uses Redis-backed session |
| 6 | postMessage wildcard origin | Tightened to platform URL |

### P1 — High

| # | Item | Change |
|---|------|--------|
| 7 | No CSRF | `X-LTI-Launch-Id` header acts as CSRF token |
| 8 | CSP `frame-ancestors *` | `settings.csp_frame_ancestors` — prod-restricted |
| 9 | No rate limiting | `slowapi` middleware, 60 RPM per learner |
| 10 | Error detail leaks | Generic errors in prod, detailed in dev |
| 11 | Missing security headers | `nosniff`, `Referrer-Policy`, `Permissions-Policy` |
| 12 | Debug page PII | Tighten to `isInstructor === true` |

### P2 — Medium

| # | Item | Change |
|---|------|--------|
| 13 | PII logging | Redact email/name at INFO level |
| 14 | No logout | `/lti/dev/logout` endpoint |
| 15 | Agent scope isolation | Fixed by PostgresSaver keyed by thread_id |
| 16 | Unencrypted Redis | Redis auth in prod (production checklist) |
| 17 | Markdown XSS | `disallowedElements` on react-markdown |
| 18 | Learner ID in URLs | Removed from URL params |
| 19 | No input max-length | `max_length=10000` on chat message |
| 20 | No DB SSL | `?sslmode=require` in prod DATABASE_URL |

### P3 — Low

| # | Item | Change |
|---|------|--------|
| 21 | Backend URL in errors | Remove hardcoded localhost |
| 22 | Hardcoded platform URL | Already uses env var |
| 23 | NEXT_PUBLIC_API_URL exposure | Document: keep empty in prod |
| 24 | No key rotation | Document rotation procedure |
| 25 | .env for secrets | Document: K8s secrets in prod |

## Phase 7: Deployment Prep (EKS/ALB/CDN)

- Next.js `output: "standalone"` + `assetPrefix` for CDN
- Conditional proxy rewrites (dev only, ALB handles prod)
- LTI config from env vars (PEM strings or file paths for K8s secrets)
- Enhanced `/health` endpoint with readiness detail
- Conditional default project ingestion (`env=local` only)

---

## Implementation Order

```
Phase 1: Settings module                              [foundation]
Phase 2: Auth middleware                              [P0 security]
Phase 3: Dev login                                    [dev ergonomics]
Phase 4: Frontend auth cleanup                        [P0 security]
Phase 5: Stateless agents                             [EKS readiness]
Phase 6: Security hardening                           [P1/P2/P3]
Phase 7: Deployment prep                              [EKS/CDN]
```

## Verification

1. `LTT_ENV=local uv run python -c "from api.settings import get_settings; print(get_settings().env)"` → "local"
2. `curl http://localhost:8000/api/v1/projects` → works (auth_enabled=False)
3. `LTT_AUTH_ENABLED=true curl http://localhost:8000/api/v1/projects` → 401
4. `curl -X POST http://localhost:8000/lti/dev/login -d '{"learner_id":"test"}'` → `{launch_id: "dev-..."}`
5. `curl -H "X-LTI-Launch-Id: dev-..." http://localhost:8000/api/v1/projects` → works
6. `uv run pytest -v` → 231 passing (auth_enabled=False by default)
7. `cd apps/web && npm run build` → standalone output
