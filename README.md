# Learning Task Tracker (LTT)

> AI-powered tutoring system that runs inside Open edX via LTI 1.3. Adapted from [beads](https://github.com/steveyegge/beads).

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)]() [![PostgreSQL](https://img.shields.io/badge/postgresql-17-blue)]() [![Next.js](https://img.shields.io/badge/next.js-16-black)]()

---

## What is LTT?

LTT provides a **data tooling layer** that enables AI tutoring agents to:
- Guide learners through structured, hierarchical projects
- Track progress per learner using a two-layer architecture
- Validate submissions as proof of work
- Provide pedagogically-aware context at every level
- Support stateless LLM agents with rich runtime tools

**Key Insight**: At any point in a learning journey, an LLM tutor should have enough **broad context** (what we're building) and **specific guidance** (what to do now) to effectively teach.

---

## Components

| Component | README | Code | Description |
|-----------|--------|------|-------------|
| **LTT Core Engine** | [services/ltt-core/](services/ltt-core/README.md) | `services/ltt-core/` | Models, services, agent tools, CLI, migrations |
| **API Server** | [services/api-server/](services/api-server/README.md) | `services/api-server/` | FastAPI REST API, LTI 1.3 endpoints |
| **AI Tutor Agent** | [services/agent-tutor/](services/agent-tutor/src/agent/README.md) | `services/agent-tutor/` | LangGraph Socratic tutoring agent |
| **Frontend** | [apps/web/](apps/web/README.md) | `apps/web/` | Next.js workspace UI (editor, chat, task tree) |
| **Infrastructure** | [infrastructure/](infrastructure/README.md) | `infrastructure/` | Docker services (Postgres, MySQL, Redis) |
| **Content** | [content/](content/README.md) | `content/` | Learning project JSON files |
| **LTI 1.3 Integration** | [docs/lti/](docs/lti/) | `services/api-server/src/api/lti/` | Full LTI spec, implementation, Open edX config |
| **Architecture Decisions** | [docs/adr/](docs/adr/) | — | ADR-001 (two-layer), ADR-002 (submissions), ADR-003 (LTI-first) |
| **Production Cleanup** | [docs/lti/cleanup/](docs/lti/cleanup/) | — | Code to remove/lock down before production |

**Full developer/LLM API reference**: [CLAUDE.md](CLAUDE.md)

---

## Architecture

### Two-Layer Design ([ADR-001](docs/adr/001-learner-scoped-task-progress.md))

```
┌─────────────────────────────────────────────────────┐
│  Template Layer (Shared Curriculum)                 │
│  tasks, learning_objectives, dependencies, content  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Instance Layer (Per-Learner)                       │
│  learner_task_progress, submissions, validations    │
└─────────────────────────────────────────────────────┘
```

One curriculum shared by thousands of learners with independent progress tracking. See [services/ltt-core/README.md](services/ltt-core/README.md) for details.

### LTI 1.3 Access Model ([ADR-003](docs/adr/003-lti-first-access-model.md))

**LTI is the only entry point for learners.** Every session starts from Open edX.

```
Open edX → POST /lti/login → OIDC redirect → POST /lti/launch → JWT validation
  → map user → persist launch → 302 /workspace/{project_id}?launch_id=...&lti=1
```

See [docs/lti/](docs/lti/) for the full spec and [docs/lti/09-architecture-overview.md](docs/lti/09-architecture-overview.md) for the component map.

### Submission-Driven Completion ([ADR-002](docs/adr/002-submission-driven-task-completion.md))

```
submit() → validate → pass? → close_task() → auto-close ancestors
```

Tasks auto-close when validation passes. Parent tasks/epics auto-close when all children complete.

---

## Quick Start

### Prerequisites

Python 3.12+, Node.js 20+, Docker, [uv](https://docs.astral.sh/uv/)

### Setup

```bash
uv sync
cd apps/web && npm install && cd ../..

# Generate RSA keys for LTI (one-time)
openssl genrsa -out configs/lti/private.key 2048
openssl rsa -in configs/lti/private.key -pubout -out configs/lti/public.key

# Start infrastructure
docker compose up -d

# Run migrations
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic upgrade head
```

### Run

```bash
# All-in-one
./tools/scripts/start-lti-dev.sh

# Or manually (each in a separate terminal)
LTI_REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 \
  --app-dir services/api-server/src --reload

cd apps/web && npm run dev

cloudflared tunnel --url http://localhost:3000  # tunnel for LTI testing
```

Then configure LTI in Open edX Studio — see [docs/lti/07-openedx-config.md](docs/lti/07-openedx-config.md).

### Verify

```bash
curl http://localhost:8000/health         # API health
curl http://localhost:8000/lti/jwks        # LTI public keys
uv run pytest services/ltt-core/tests/ -q  # Core tests
```

---

## Project Structure

```
beadslocal/
├── services/
│   ├── ltt-core/               # Core engine — README inside
│   ├── api-server/             # FastAPI API — README inside
│   └── agent-tutor/            # AI tutor — README inside
│
├── apps/web/                   # Next.js frontend — README inside
│
├── infrastructure/             # Docker services — README inside
│   └── docker/docker-compose.yml
│
├── content/                    # Learning projects — README inside
│   └── projects/
│
├── configs/lti/                # Platform config + RSA keys
│
├── docs/
│   ├── lti/                    # LTI 1.3 spec (10 docs + cleanup audit)
│   ├── adr/                    # Architecture Decision Records
│   └── schema/                 # Project ingestion JSON schema
│
├── tools/scripts/              # start-lti-dev.sh, utilities
├── CLAUDE.md                   # Full developer/LLM API reference
└── BUILD-STATUS.md             # Test results by phase
```

---

## Key Concepts

### Hierarchical Tasks

```
Project → Epic → Task → Subtask
proj-a1b2  .1     .1.1   .1.1.1
```

Unlimited nesting. Context flows from broad (project narrative) to specific (subtask acceptance criteria). See [services/ltt-core/README.md](services/ltt-core/README.md).

### Pedagogical Guidance

```json
{
  "tutor_guidance": {
    "teaching_approach": "Start with real-world context before SQL",
    "common_mistakes": ["Using = instead of >"],
    "hints_to_give": ["Which operator means 'greater than'?"]
  },
  "narrative_context": "You are analyzing water quality data from rural communities..."
}
```

These fields guide **HOW** LLM tutors teach, not just **WHAT** they teach. `content` is learner-facing material; `tutor_guidance` is meta-guidance for the AI agent.

### Learning Objectives (Bloom's Taxonomy)

Levels: remember → understand → apply → analyze → evaluate → create. Achievement is derived from passing validations, not stored separately.

---

## Development

### Tests

```bash
uv run pytest services/ltt-core/tests/ -v   # Core (167 tests)
uv run pytest services/agent-tutor/tests/ -v # Agent (31 tests)
uv run pytest -v                             # All (231 tests)
```

98% coverage. See [BUILD-STATUS.md](BUILD-STATUS.md).

### Code Quality

```bash
uv run ruff check services/ tools/
uv run ruff format services/ tools/
```

### Migrations

```bash
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic upgrade head
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic revision --autogenerate -m "description"
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection (default: dev credentials) |
| `LTI_REDIS_URL` | For LTI | Redis URL. If unset, LTI is disabled. |
| `LTT_FRONTEND_URL` | No | Where `/lti/launch` redirects (default: `http://localhost:3000`) |
| `LTI_PLATFORM_URL` | No | CSP `frame-ancestors` (default: `https://imbizo.alx-ai-tools.com`) |
| `DEBUG` | No | Enables `/lti/debug/*` endpoints |
| `NEXT_PUBLIC_DEBUG` | No | Enables debug button in frontend |
| `ANTHROPIC_API_KEY` | For agent | Claude API key for tutoring agent |

---

## Implementation Status

**All Core Phases Complete** — 231 tests, all passing.

| Phase | Module | Tests |
|-------|--------|-------|
| 1-5 | Core Engine (data, tasks, deps, submissions, learning) | 118 |
| 7-8 | Agent Tools + CLI/Ingestion | 49 |
| E2E | End-to-End Integration | 15 |
| Agent | AI Tutor + Learner Simulation | 31 |
| LTI | OIDC login, JWT launch, AGS grades | Manual |

### Next Steps

- [ ] LTI auth middleware on API endpoints ([cleanup plan](docs/lti/cleanup/))
- [ ] Remove standalone mode code (home page, cookie learners)
- [ ] Custom validation rules (SQL result checks, code tests)
- [ ] Production deployment (static domain, tighten CORS/CSP)

---

## Contributing

- Modern Python 3.12+, async-first, Pydantic for validation, Ruff for linting
- All new features must have tests (maintain >95% coverage)
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`

---

## License

MIT

---

## Acknowledgments

Adapted from [beads](https://github.com/steveyegge/beads) by Steve Yegge. Core architectural patterns (hierarchical IDs, dependency resolution, ready work calculation) borrowed with gratitude.
