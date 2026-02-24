# LTT Frontend

> Next.js workspace UI — task navigation, code editor, AI chat, embedded in Open edX via LTI.

---

## What This Is

The frontend provides the learner-facing workspace:

- **Task tree** — hierarchical project navigator with progress indicators
- **Code editor** — CodeMirror-based SQL and Python editors
- **SQL.js** — in-browser SQLite for learner SQL execution
- **AI chat** — SSE-streamed conversation with the Socratic tutor agent
- **LTI context** — iframe-aware, reads launch params, injects `X-LTI-Launch-Id` header

Runs inside an iframe when launched from Open edX via LTI 1.3.

---

## Directory Layout

```
src/
├── app/                     # Next.js app router
│   ├── layout.tsx           #   Root layout
│   ├── page.tsx             #   Home page (project list — standalone only)
│   ├── workspace/           #   Main workspace route
│   ├── project/             #   Project selection route
│   └── debug/               #   Debug page (dev only)
│
├── components/
│   ├── chat/                #   AI tutor chat panel
│   ├── workspace/           #   Editor, results, toolbar
│   ├── project/             #   Task tree, progress display
│   ├── shared/              #   DebugButton, common components
│   ├── ui/                  #   Radix UI primitives
│   └── providers.tsx        #   React Query, theme providers
│
├── lib/
│   ├── lti.ts               #   LTI context (parse, store, iframe detect, resize)
│   ├── api.ts               #   lttFetch() — API client with LTI header injection
│   ├── learner.ts           #   Learner ID management (LTI-aware)
│   ├── sql-engine.ts        #   SQL.js browser engine
│   ├── python-engine.ts     #   Pyodide browser engine
│   └── utils.ts             #   General utilities
│
├── stores/
│   └── workspace-store.ts   #   Zustand store for workspace state
│
└── hooks/                   #   Custom React hooks
```

---

## LTI Integration

When launched from Open edX, the frontend receives URL params from the LTI launch redirect:

```
/workspace/{project_id}?launch_id=xxx&learnerId=yyy&lti=1
```

### Key files

- **[lti.ts](src/lib/lti.ts)** — `parseLTIContext()` reads URL params, `storeLTIContext()`/`getLTIContext()` use `sessionStorage`, `isInIframe()` detects embedding, `requestIframeResize()` sends postMessage to parent
- **[api.ts](src/lib/api.ts)** — `lttFetch()` wraps `fetch()` to attach `X-LTI-Launch-Id` and `ngrok-skip-browser-warning` headers
- **[learner.ts](src/lib/learner.ts)** — `getOrCreateLearnerId()` returns LTI learner ID when in LTI context, falls back to cookie for standalone dev

### Proxy rewrites

[next.config.ts](next.config.ts) proxies backend routes so the tunnel exposes a single origin:

```
/lti/*     → http://localhost:8000/lti/*
/api/*     → http://localhost:8000/api/*
/health    → http://localhost:8000/health
```

---

## Running

```bash
npm install
npm run dev        # http://localhost:3000
```

For LTI testing, start the backend and a tunnel:

```bash
# Backend (separate terminal)
LTT_REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 \
  --app-dir services/api-server/src --reload

# Tunnel (separate terminal)
cloudflared tunnel --url http://localhost:3000
```

Or use `./tools/scripts/start-lti-dev.sh` to start everything at once.

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Backend URL for proxy rewrites (default: `http://localhost:8000`) |
| `NEXT_PUBLIC_DEBUG` | Enables debug button in UI |
| `LTI_PLATFORM_URL` | CSP `frame-ancestors` value (default: `https://imbizo.alx-ai-tools.com`) |

---

## Tech Stack

- **Next.js 16** (App Router, Turbopack)
- **TypeScript**
- **Tailwind CSS v4**
- **Radix UI** — accessible component primitives
- **CodeMirror** — SQL and Python editors
- **SQL.js** — in-browser SQLite for learner queries
- **Zustand** — lightweight state management
- **React Query** — server state / data fetching

---

## Standalone vs LTI Mode

| Concern | Standalone (dev) | LTI (production) |
|---------|------------------|-------------------|
| Learner ID | Cookie-based, auto-generated | From LTI launch JWT |
| Project selection | Home page → project list | `custom.project_id` in LTI params |
| API auth | None (raw `learner_id`) | `X-LTI-Launch-Id` header |
| Embedding | Direct browser tab | iframe inside Open edX |

Standalone mode exists for development convenience. Production uses LTI exclusively — see [ADR-003](../../docs/adr/003-lti-first-access-model.md).

---

## Related Docs

- [docs/lti/05-frontend-iframe.md](../../docs/lti/05-frontend-iframe.md) — iframe detection, resize, cookie handling
- [docs/lti/cleanup/](../../docs/lti/cleanup/) — Standalone code to remove for production
