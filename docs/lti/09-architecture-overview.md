# LTI Architecture Overview

> How every piece fits together in production. This is the single source of truth for the LTI-first architecture.

---

## Access Model

**LTI is the only entry point for learners.** There is no standalone mode, no project picker, no self-service learner creation. Every session begins when a learner clicks an LTI link inside Open edX.

```
Open edX (imbizo.alx-ai-tools.com)
  │
  │  1. Learner clicks LTI link in course unit
  │
  ▼
POST /lti/login          ← OIDC initiation (validates platform, sets state cookie)
  │
  │  2. Redirect to Open edX auth endpoint
  │
  ▼
POST /lti/launch         ← JWT validation (signed id_token from platform)
  │
  │  3. Extract identity (sub, iss, name, email)
  │  4. Map to LTT learner (create or lookup via lti_user_mappings)
  │  5. Persist launch to DB (lti_launches) + Redis cache
  │  6. Determine project_id from custom params
  │
  ▼
302 → /workspace/{project_id}?launch_id=...&learnerId=...&lti=1
  │
  │  7. Next.js reads URL params, stores LTI context in sessionStorage
  │  8. All subsequent API calls include X-LTI-Launch-Id header
  │
  ▼
Normal operation: task navigation, chat, submissions, grade passback
```

---

## Component Map

### Backend (Python)

| Component | Path | Purpose |
|-----------|------|---------|
| **LTI adapter** | `services/api-server/src/api/lti/adapter.py` | PyLTI1p3 wrappers for FastAPI (request, cookie, redirect, OIDC, message launch) |
| **Config loader** | `services/api-server/src/api/lti/config.py` | Loads `configs/lti/platform.json` + RSA keys. Env overrides: `LTI_PLATFORM_CONFIG`, `LTI_PRIVATE_KEY`, `LTI_PUBLIC_KEY` |
| **Redis storage** | `services/api-server/src/api/lti/storage.py` | `RedisLaunchDataStorage(LaunchDataStorage)` for nonces, state, launch data. TTL-based. |
| **Routes** | `services/api-server/src/api/lti/routes.py` | `/lti/login`, `/lti/launch`, `/lti/jwks`, `/lti/debug/*` |
| **User mapping** | `services/api-server/src/api/lti/users.py` | `get_or_create_lti_learner()` — maps LTI `(sub, iss)` to LTT `learner_id` |
| **Grades** | `services/api-server/src/api/lti/grades.py` | `send_grade()` via AGS, `maybe_send_grade()` for automatic passback |
| **Middleware** | `services/api-server/src/api/lti/middleware.py` | `LTIContext` dataclass, `resolve_launch()` from Redis |
| **App integration** | `services/api-server/src/api/app.py` | LTI router registered, CSP middleware, Redis init in lifespan |

### Database

| Table | Model | Purpose |
|-------|-------|---------|
| `lti_user_mappings` | `LTIUserMapping` | Maps `(lti_sub, lti_iss)` → `learner_id`. Unique constraint. |
| `lti_launches` | `LTILaunch` | Persists active launch data (survives Redis restart). FK to `learners`. |

### Frontend (TypeScript)

| File | Purpose |
|------|---------|
| `apps/web/src/lib/lti.ts` | `parseLTIContext()`, `storeLTIContext()`, `getLTIContext()`, `isInIframe()`, `requestIframeResize()` |
| `apps/web/src/lib/api.ts` | `lttFetch()` wrapper attaches `X-LTI-Launch-Id` header |
| `apps/web/src/lib/learner.ts` | `getOrCreateLearnerId()` — LTI context takes priority over cookie |
| `apps/web/next.config.ts` | Proxy rewrites (`/lti/*` → FastAPI), CSP `frame-ancestors` |

### Infrastructure

| Component | Config | Purpose |
|-----------|--------|---------|
| Redis | `infrastructure/docker/docker-compose.yml` | LTI state cache (nonces, launches). `redis:7-alpine` on port 6379. |
| RSA keys | `configs/lti/private.key`, `configs/lti/public.key` | JWT signing/verification. Private key is gitignored. |
| Platform config | `configs/lti/platform.json` | Issuer URL, client_id, auth endpoints, deployment IDs |

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LTT_REDIS_URL` | Yes (for LTI) | — | Redis connection URL. If unset, LTI endpoints are disabled. |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev` | PostgreSQL connection |
| `LTT_FRONTEND_URL` | No | `http://localhost:3000` | Where `/lti/launch` redirects after JWT validation |
| `LTI_PLATFORM_URL` | No | `https://imbizo.alx-ai-tools.com` | Used in CSP `frame-ancestors` |
| `LTI_PLATFORM_CONFIG` | No | `configs/lti/platform.json` | Override platform config path |
| `LTI_PRIVATE_KEY` | No | `configs/lti/private.key` | Override private key path |
| `LTI_PUBLIC_KEY` | No | `configs/lti/public.key` | Override public key path |
| `DEBUG` | No | — | Enables `/lti/debug/*` endpoints |
| `NEXT_PUBLIC_DEBUG` | No | — | Enables debug button in frontend |

---

## Security Model

1. **Authentication**: LTI 1.3 JWT, signed by the platform, validated by our tool using the platform's public key set
2. **Identity**: `sub` claim (platform user ID) + `iss` claim (platform URL) = unique identity
3. **Authorization**: Learner can only access the project specified in `custom.project_id` from the launch
4. **Session**: `launch_id` stored in sessionStorage (iframe-scoped, not cross-tab)
5. **Grade passback**: Uses OAuth 2.0 client credentials grant (tool → platform) for AGS
6. **CSP**: `frame-ancestors *` allows embedding (tightened to specific platform in production)
7. **CORS**: Currently `*` — tighten for production
