# LTI 1.3 Integration: LTT on Open edX

> Specification for integrating the Learning Task Tracker into Open edX via LTI 1.3 with LTI Advantage.

**Target platform**: https://imbizo.alx-ai-tools.com/

---

## Why LTI 1.3?

| Requirement | LTI 1.3 | XBlock | MFE Plugin | Django Plugin | Raw iframe |
|---|---|---|---|---|---|
| Keep FastAPI backend | Yes | No | No | No | Yes |
| Keep Next.js frontend | Yes | No | No | Yes (proxy) | Yes |
| Real-time AI chat (SSE) | Yes | Polling only | N/A | N/A | Yes |
| Grade passback | Yes (AGS) | Yes | No | Possible | No |
| User identity | Yes (JWT) | Yes | Yes | Yes | No |
| Independent deployment | Yes | No | Partial | No | Yes |
| Works with other LMSes | Yes | No | No | No | N/A |

LTI 1.3 lets us keep our entire stack running independently while Open edX embeds it in an iframe with standards-based authentication and grade passback.

---

## Architecture

```
Open edX (imbizo.alx-ai-tools.com)
  +---------------------------------------------------------+
  |  Course Unit                                            |
  |  +----------------------------------------------------+ |
  |  | LTI Consumer XBlock (iframe)                       | |
  |  |                                                    | |
  |  |  +----------------------------------------------+  | |
  |  |  | LTT Next.js Frontend                         |  | |
  |  |  | (loaded from ngrok / your domain)            |  | |
  |  |  |                                              |  | |
  |  |  |  [AI Tutor Chat]     [Code Editor]           |  | |
  |  |  |  [Task Progress]     [Submissions]           |  | |
  |  |  |                                              |  | |
  |  |  |  SSE/REST  <------->  FastAPI Backend         |  | |
  |  |  |                       + PostgreSQL            |  | |
  |  |  |                       + LangGraph Agent       |  | |
  |  |  |                       + LTI 1.3 endpoints     |  | |
  |  |  +----------------------------------------------+  | |
  |  +----------------------------------------------------+ |
  +---------------------------------------------------------+
           ^                            |
           |   LTI 1.3 Launch (JWT)     |
           |   NRPS (user identity)     |
           |                            v
           +---- AGS Grade Passback ----+
```

### What stays the same

- FastAPI API server (`services/api-server/`)
- LangGraph AI tutoring agent (`services/agent-tutor/`)
- LTT core engine (`services/ltt-core/`)
- PostgreSQL + MySQL databases
- Next.js frontend (`apps/web/`)

### What we add

| Component | Description | Location |
|---|---|---|
| LTI endpoints | OIDC login, launch, JWKS | `services/api-server/src/api/lti/` |
| FastAPI adapter | PyLTI1p3 wrappers for FastAPI | `services/api-server/src/api/lti/adapter.py` |
| Launch data storage | Redis-backed cache for LTI state | `services/api-server/src/api/lti/storage.py` |
| User mapping | LTI sub claim to LTT learner_id | `services/api-server/src/api/lti/users.py` |
| Grade service | AGS grade passback on task completion | `services/api-server/src/api/lti/grades.py` |
| LTI config | Platform registration + RSA keys | `configs/lti/` |
| Frontend tweaks | iframe detection, auto-resize | `apps/web/src/lib/lti.ts` |

---

## Data Flow

### 1. LTI Launch (one-time per session)

```
1. Learner clicks "LTT Activity" in Open edX course
2. Open edX sends OIDC login request → POST /lti/login
3. Tool validates, redirects to Open edX auth endpoint
4. Open edX creates signed JWT, POSTs → POST /lti/launch
5. Tool validates JWT, extracts user identity
6. Tool maps LTI sub → LTT learner_id (create if needed)
7. Tool stores launch data in Redis (keyed by launch_id)
8. Tool redirects to Next.js app with ?launch_id=xxx&project_id=yyy
```

### 2. Normal Operation (after launch)

```
1. Next.js reads launch_id from URL, stores in state
2. API calls include launch_id header (replaces raw learner_id)
3. Backend resolves launch_id → learner_id from Redis cache
4. Chat, task operations, submissions work as before
5. SSE streaming works natively (iframe loads our domain)
```

### 3. Grade Passback (on task completion)

```
1. Learner submits work via submit tool
2. Validation passes, task closes
3. Backend calculates project progress (e.g., 15/42 tasks = 35.7%)
4. Backend calls AGS endpoint to send score to Open edX
5. Open edX gradebook updates automatically
```

---

## Documents

### Specification (pre-implementation)

| Doc | Description |
|---|---|
| [01-lti-protocol.md](01-lti-protocol.md) | LTI 1.3 OIDC flow, JWT claims, security model |
| [02-implementation.md](02-implementation.md) | FastAPI endpoints, PyLTI1p3 adapter, file layout |
| [03-user-mapping.md](03-user-mapping.md) | LTI identity to LTT learner mapping |
| [04-grade-passback.md](04-grade-passback.md) | AGS grade sync on task/project completion |
| [05-frontend-iframe.md](05-frontend-iframe.md) | Next.js iframe detection, resize, cookie handling |
| [06-ngrok-setup.md](06-ngrok-setup.md) | Local dev tunnel to imbizo.alx-ai-tools.com |
| [07-openedx-config.md](07-openedx-config.md) | Studio LTI component configuration |
| [08-testing.md](08-testing.md) | End-to-end testing checklist |

### Architecture & production

| Doc | Description |
|---|---|
| [09-architecture-overview.md](09-architecture-overview.md) | How everything fits together — component map, env vars, security model |
| [10-production-checklist.md](10-production-checklist.md) | What must be done before going live |
| [cleanup/](cleanup/) | **Code outside the LTI path that must be removed or locked down** |

---

## Quick Start (Dev)

```bash
# 1. Generate RSA keys (if not already present)
openssl genrsa -out configs/lti/private.key 2048
openssl rsa -in configs/lti/private.key -pubout -out configs/lti/public.key

# 2. Start infrastructure
docker-compose up -d  # postgres, mysql, redis

# 3. Run migrations
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic upgrade head

# 4. Start API server
LTI_REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 \
  --app-dir services/api-server/src

# 5. Start frontend
cd apps/web && npm run dev  # localhost:3000

# 6. Start tunnel (pick one)
cloudflared tunnel --url http://localhost:3000  # free, random URL
# or
ngrok http 3000 --domain your-reserved.ngrok-free.app  # stable URL

# 7. Configure LTI in Open edX Studio (see 07-openedx-config.md)

# 8. Launch from Open edX course
```

Or use the convenience script:

```bash
./tools/scripts/start-lti-dev.sh          # without tunnel
./tools/scripts/start-lti-dev.sh --ngrok  # with ngrok
```
