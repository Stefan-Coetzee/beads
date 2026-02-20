# Workspace Architecture — Server-Side Options

> Can we connect to a real Jupyter/Marimo server instead of running everything in-browser?
> Can the LLM tutor act as a collaborator in the learner's session?

---

## The Big Picture

The current setup runs Pyodide and sql.js entirely in the browser. This works but has limits: no terminal, no filesystem, heavy WASM downloads, infinite loops freeze the tab. The alternative is a **server-side kernel** where the browser is just a thin editor and the real execution happens remotely.

The good news: Jupyter's API surface is **much richer** than expected, and a new wave of MCP-based AI collaboration tools has landed in 2025-2026 that solve the "LLM reads the notebook" problem natively.

---

## Approach A: JupyterHub + AI Tutor as Service

**Architecture:**
```
Learner's browser (JupyterLab UI)
     │
     ▼
JupyterHub (provisions per-learner servers)
     │
     ├── Learner's Jupyter Server (isolated container)
     │     ├── Python kernel (real CPython, not WASM)
     │     ├── SQL via ipython-sql or sqlite3
     │     ├── Terminal (real bash/zsh shell)
     │     └── Notebook files (persistent storage)
     │
     └── LTT Tutor Service (our backend)
           ├── JupyterHub service token (admin_access)
           ├── Reads cells via Contents API
           ├── Executes code via Kernel WebSocket
           ├── Joins notebook via RTC/CRDT (Y.js)
           └── Monitors terminal sessions
```

**How it works:**

1. **JupyterHub** provisions a per-learner Jupyter server (Docker container, Kubernetes pod, etc). Each learner gets an isolated environment with a real Python kernel, filesystem, and terminal.

2. **Our tutor backend** registers as a JupyterHub **Service** with scoped RBAC permissions. It gets a service token that can access any learner's server.

3. **Reading notebook contents** — the Jupyter Contents API (`GET /api/contents/notebook.ipynb`) returns the full notebook JSON including all cells, outputs, and metadata. No iframe bridge needed.

4. **Executing code** — the Kernel WebSocket API (`ws://server/api/kernels/{id}/channels`) lets our backend send `execute_request` messages to the learner's kernel and receive `stream`, `execute_result`, and `error` responses. The tutor can run diagnostic code in the learner's kernel.

5. **Real-time collaboration** — `jupyter-collaboration` (v4.2.1, official Jupyter project) uses Y.js CRDTs. The tutor can join the collaboration session and see cell edits in real-time. Changes by the tutor appear instantly in the learner's UI.

6. **Terminal access** — Jupyter's Terminal API creates real PTY sessions. `POST /api/terminals` creates a terminal, `ws://server/terminals/websocket/{name}` gives bidirectional shell access. Perfect for cyber exercises.

**What this gives us:**
| Capability | How |
|-----------|-----|
| Python notebook | JupyterLab native |
| SQL editor | `ipython-sql` magic or dedicated SQL kernel |
| Terminal (cyber) | Jupyter Terminal API + xterm.js |
| LLM reads cells | Contents API or RTC/CRDT |
| LLM writes cells | Contents API PUT or RTC/CRDT |
| LLM executes code | Kernel WebSocket `execute_request` |
| No WASM download | Real server-side kernel |
| Infinite loop safety | Kernel interrupt API (`POST /api/kernels/{id}/interrupt`) |
| Package installation | `pip install` in real environment |
| File system access | Real filesystem in container |

**What this costs:**
- Server infrastructure per learner (containers, compute, storage)
- JupyterHub deployment and maintenance
- Network latency for every keystroke if using RTC
- Authentication/security complexity
- No offline capability

---

## Approach B: JupyterHub + MCP Bridge (AI Agent Pattern)

This is the **emerging pattern** in the Jupyter ecosystem as of 2025-2026. Instead of custom API integration, use the **Model Context Protocol (MCP)** to bridge the LLM to Jupyter.

**Tools available now:**

| Project | What it does | Maturity |
|---------|-------------|----------|
| `jupyter-collaboration-mcp` | Bridges MCP to Y.js/CRDT layer. Agent joins as real-time collaborator. | Active, early |
| `jupyter-ai-agents` (Datalayer) | Full AI agent framework — RTC + kernel + Pydantic AI. Uses Claude. | Active, on PyPI |
| `mcp-jupyter` | Lightweight MCP server for notebook operations | Active, on PyPI |
| `notebook-intelligence` | AI agents for JupyterLab | Active, on PyPI |

**The `jupyter-ai-agents` pattern:**
```
LLM (Claude)
  │
  ▼
Pydantic AI Agent
  │
  ├── Jupyter NbModel Client (RTC WebSocket → read/write cells)
  ├── Jupyter Kernel Client (WebSocket → execute code, capture output)
  └── Jupyter Contents Client (REST → read/write files)
```

The agent connects via RTC and appears as a collaborator. The learner sees the AI's cursor, edits, and cell insertions in real-time — like Google Docs with an AI pair programmer.

**Advantage over Approach A:** We don't build the Jupyter integration ourselves — we use established MCP tools. Our tutor agent just needs to be an MCP client.

**Risk:** These MCP tools are new (2025). APIs may change. But the direction is clear — this is where the ecosystem is heading.

---

## Approach C: Marimo Server + FastAPI Mount

**Architecture:**
```
Our FastAPI backend
  │
  ├── /api/v1/...          (LTT API — tasks, progress, chat)
  ├── /workspace/{id}      (marimo app, mounted via create_asgi_app())
  └── /api/v1/tutor/...    (LLM tutor — reads marimo state via app.run())
```

**How it works:**

1. Marimo notebooks are pure Python files (not JSON). Mount them into FastAPI with `marimo.create_asgi_app()`.

2. The tutor backend can call `app.run()` to execute all cells and get outputs + variable definitions programmatically.

3. Marimo has built-in CRDT collaboration (via Loro, a Rust CRDT library) — multiple users can edit simultaneously.

4. Notebooks are git-friendly (plain Python), which is great for curriculum versioning.

**Limitations:**
- No terminal access (marimo is a notebook, not a full IDE)
- No individual cell manipulation API yet (GitHub issue #4345 is open)
- Less mature AI agent ecosystem compared to Jupyter
- `app.run()` executes the whole notebook — no per-cell execution from outside
- Embedding in a custom React UI is iframe-only (no native React components beyond the immature `@marimo-team/blocks`)

**Best for:** Pure Python notebook exercises where you want simple deployment and don't need terminal or fine-grained AI cell access.

---

## Approach D: Hybrid — In-Browser Default, Server Fallback

Keep the current Pyodide/sql.js in-browser setup as the default, but add a server-side backend for when it's needed.

```
Learner opens workspace
  │
  ├── Small device / slow connection?
  │     └── Connect to server-side kernel (Jupyter/container)
  │
  └── Capable device?
        └── Run Pyodide + sql.js in browser (current setup)
```

**The engines already share a common interface** (`executePython(code) → PythonResult`). Swapping the in-browser engine for an API call to a remote kernel is a function signature swap, not an architecture change.

**For the LLM tutor**, both paths work:
- In-browser: tutor reads cell contents from the Zustand store (current approach)
- Server-side: tutor reads cell contents from Jupyter Contents API or RTC

**Best for:** PoC now, production later. Ship with in-browser, add server fallback when infrastructure is ready.

---

## Approach E: Our UI + Remote Kernel (No JupyterLab UI)

Keep our custom React workspace UI but replace the in-browser Pyodide/sql.js with a remote execution backend.

```
Our React UI (CodeMirror editors, results panels, chat)
     │
     ▼
Our API server
     │
     ├── Jupyter Kernel Gateway (headless — no UI, just kernels)
     │     ├── Python kernel per learner
     │     └── SQL kernel or ipython-sql
     │
     └── Terminal backend (node-pty or terminado)
           └── xterm.js in browser connects via WebSocket
```

**Jupyter Kernel Gateway** runs kernels without the JupyterLab UI. Our backend sends `execute_request` messages over WebSocket, gets results back, and forwards them to our React UI.

**Advantage:** We keep full control of the UI and LLM integration. The kernel is just a compute backend.

**Disadvantage:** We lose JupyterLab's rich output rendering (matplotlib plots, ipywidgets, etc). We'd need to handle MIME-type output ourselves.

---

## Comparison

| | In-Browser (current) | JupyterHub + MCP | Marimo Server | Hybrid | Our UI + Remote Kernel |
|---|---|---|---|---|---|
| **Infrastructure** | None | Heavy (Hub + containers) | Medium (FastAPI) | Adaptive | Medium (Gateway) |
| **Offline capable** | Yes | No | No | Partially | No |
| **Terminal (cyber)** | No | Yes (native) | No | Only server path | Yes (custom) |
| **LLM reads cells** | Zustand store | Contents API / RTC / MCP | `app.run()` | Both | Our API |
| **Real Python** | No (Pyodide) | Yes | Yes (server) / No (WASM) | Both | Yes |
| **Infinite loop kill** | Worker terminate | Kernel interrupt API | N/A | Both | Kernel interrupt |
| **Bundle size** | ~15 MB (Pyodide) | ~0 (thin client) | ~0 or ~15 MB | Varies | ~0 (thin client) |
| **Deployment simplicity** | Static files | Complex | Medium | Medium | Medium |
| **Time to implement** | Done | 2-4 weeks | 1-2 weeks | 1 week (fallback) | 2-3 weeks |
| **Maturity risk** | Stable | Established (Hub) + new (MCP) | Growing | Low | Established |

---

## Recommendation for PoC vs Production

### PoC (now)
Keep Approach D (hybrid). The in-browser engines work today. The Web Worker timeout handles infinite loops. The tutor reads from the store. Ship it.

### Production path
**Approach B (JupyterHub + MCP)** is the strongest long-term play:

1. JupyterHub is battle-tested at scale (used by universities, NASA, Berkeley, etc.)
2. Per-learner isolation is built in (Docker spawner, Kubernetes spawner)
3. The MCP bridge pattern (`jupyter-ai-agents`, `jupyter-collaboration-mcp`) means our tutor joins as a real-time collaborator — no custom API plumbing
4. Terminal access is free (Jupyter Terminal API)
5. SQL can run via `ipython-sql` magic or a separate SQL kernel
6. The ecosystem is investing heavily in AI collaboration — we ride that wave instead of building our own

**The migration path is incremental:**
1. PoC ships with in-browser Pyodide/sql.js (done)
2. Add JupyterHub deployment alongside our app
3. Add kernel gateway as execution backend (swap `executePython` implementation)
4. Add terminal workspace type using Jupyter Terminal API
5. Connect tutor to learner notebooks via MCP bridge
6. Phase out in-browser engines (or keep as offline fallback)

---

## Key APIs to Know

**Jupyter Server REST (reading notebooks):**
```
GET /api/contents/notebook.ipynb    → full notebook JSON with all cells
PUT /api/contents/notebook.ipynb    → save modified notebook
```

**Jupyter Kernel WebSocket (executing code):**
```
ws://server/api/kernels/{id}/channels
→ send: { msg_type: "execute_request", content: { code: "print(1)" } }
← recv: { msg_type: "stream", content: { text: "1\n" } }
← recv: { msg_type: "execute_reply", content: { status: "ok" } }
```

**Jupyter Terminal WebSocket (shell access):**
```
POST /api/terminals              → creates terminal, returns { name }
ws://server/terminals/websocket/{name}  → bidirectional PTY
```

**JupyterHub Service Token (accessing learner servers):**
```python
headers = {"Authorization": f"token {service_token}"}
requests.get(f"http://hub/user/{learner}/api/contents/", headers=headers)
```

---

## References

- [Jupyter Server REST API](https://jupyter-server.readthedocs.io/en/latest/developers/rest-api.html)
- [Jupyter Messaging Protocol](https://jupyter-client.readthedocs.io/en/stable/messaging.html)
- [JupyterHub Services + RBAC](https://jupyterhub.readthedocs.io/en/stable/reference/services.html)
- [jupyter-collaboration (RTC)](https://github.com/jupyterlab/jupyter-collaboration) — v4.2.1, official Jupyter
- [jupyter-ai-agents](https://github.com/datalayer/jupyter-ai-agents) — AI agent framework for JupyterLab
- [jupyter-collaboration-mcp](https://glama.ai/mcp/servers/@complyue/jupyter-collaboration-mcp) — MCP bridge to CRDT
- [mcp-jupyter](https://pypi.org/project/mcp-jupyter/) — lightweight MCP server
- [Jupyter Kernel Gateway](https://jupyter-kernel-gateway.readthedocs.io/)
- [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/)
- [Marimo Programmatic API](https://docs.marimo.io/guides/deploying/programmatically/)
- [Marimo CRDT Collaboration](https://github.com/marimo-team/marimo/discussions/1664)
