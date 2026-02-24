# API Server

> FastAPI REST API — serves the frontend, the AI tutor agent, and LTI 1.3 endpoints.

---

## What This Is

The API server is the HTTP layer between the frontend/LMS and the LTT core engine. It provides:

- **LTI 1.3 endpoints** — OIDC login, JWT launch, JWKS, grade passback
- **Frontend endpoints** — project tree, task details, start/submit actions
- **Agent endpoints** — chat (sync + SSE streaming), session management
- **Health check** — `/health`

Depends on `ltt-core` for all business logic.

---

## Endpoints

### LTI (`/lti/*`)

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/lti/login` | OIDC login initiation |
| POST | `/lti/launch` | JWT validation, user mapping, redirect to frontend |
| GET | `/lti/jwks` | Tool's public key set |
| GET | `/lti/debug/launches` | List active launches (debug only) |
| GET | `/lti/debug/launch/{id}` | Inspect launch data (debug only) |
| POST | `/lti/debug/simulate` | Simulate a launch (debug only) |

Full LTI spec: [docs/lti/](../../docs/lti/)

### Frontend (`/api/v1/*`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/projects` | List all projects |
| GET | `/api/v1/project/{id}/tree` | Project tree with learner progress |
| GET | `/api/v1/task/{id}` | Task details (blocking info, content, guidance) |
| GET | `/api/v1/project/{id}/ready` | Ready tasks for learner |
| POST | `/api/v1/task/{id}/start` | Start working on a task |
| POST | `/api/v1/task/{id}/submit` | Submit work for validation |
| GET | `/api/v1/project/{id}/database` | SQL schema for browser SQL.js |

All frontend endpoints accept `learner_id` as a query param or in the request body.

> **Production note**: These endpoints currently accept raw `learner_id`. In production, `learner_id` will be resolved from the `X-LTI-Launch-Id` header via LTI middleware. See [cleanup plan](../../docs/lti/cleanup/).

### Agent (`/api/v1/*`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/chat` | Send message, get full response |
| POST | `/api/v1/chat/stream` | Send message, stream SSE response |
| POST | `/api/v1/session` | Create agent session |
| GET | `/api/v1/session/{id}/state` | Get session state |

### Health

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status + LTI enabled flag |

---

## Directory Layout

```
src/api/
├── app.py               # FastAPI app, lifespan, middleware (CORS, CSP)
├── database.py          # SQLAlchemy async engine + session factory
├── routes.py            # Agent endpoints (chat, stream, session)
├── frontend_routes.py   # Frontend endpoints (projects, tasks, submit)
├── agents.py            # Agent manager (LangGraph agent pool)
│
└── lti/                 # LTI 1.3 integration
    ├── adapter.py       #   PyLTI1p3 FastAPI wrappers
    ├── config.py        #   Platform config + RSA key loader
    ├── routes.py        #   /lti/login, /lti/launch, /lti/jwks, debug
    ├── storage.py       #   Redis-backed launch data storage
    ├── users.py         #   LTI sub → LTT learner_id mapping
    ├── grades.py        #   AGS grade passback
    └── middleware.py     #   LTI context resolution from Redis
```

---

## Running

```bash
# With LTI (requires Redis)
LTT_REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 \
  --app-dir services/api-server/src --reload

# Without LTI (LTI endpoints disabled)
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 \
  --app-dir services/api-server/src --reload
```

Or use the convenience script: `./tools/scripts/start-lti-dev.sh`

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev` | PostgreSQL |
| `LTT_REDIS_URL` | For LTI | — | Redis URL. If unset, LTI is disabled. |
| `LTT_FRONTEND_URL` | No | `http://localhost:3000` | Where `/lti/launch` redirects |
| `LTI_PLATFORM_URL` | No | `https://imbizo.alx-ai-tools.com` | CSP `frame-ancestors` |
| `DEBUG` | No | — | Enables `/lti/debug/*` endpoints |

---

## Middleware

- **CSP**: `frame-ancestors *` (tighten to specific platform URL in production)
- **CORS**: `allow_origins=["*"]` (tighten in production)
- LTI launch sets `SameSite=None; Secure` cookies for iframe compatibility

---

## Dependencies

```
ltt-core, fastapi, uvicorn, PyLTI1p3>=2.0.0, redis>=5.0.0, cryptography>=42.0.0
```

---

## Related Docs

- [docs/lti/](../../docs/lti/) — Full LTI 1.3 spec and implementation details
- [docs/lti/cleanup/](../../docs/lti/cleanup/) — Code that needs auth middleware for production
- [docs/lti/09-architecture-overview.md](../../docs/lti/09-architecture-overview.md) — Component map
