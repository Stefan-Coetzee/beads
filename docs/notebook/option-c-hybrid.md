# Option C: Hybrid — In-Browser Default, Server Upgrade

> Ship now with in-browser Pyodide + sql.js. Add JupyterHub as an
> upgrade path when infrastructure is ready. Same React UI, same
> tutor, swappable execution backend.

---

## Summary

Build the notebook UI once (Option A's custom frontend). The execution layer is behind an interface: in-browser Pyodide by default, remote Jupyter kernel when a server is available. The LLM tutor reads cells from the same React state regardless of backend. Terminal cells are disabled in browser mode, enabled in server mode.

**One codebase, two execution backends, progressive enhancement.**

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Our React App (always the same)                    │
│                                                     │
│  ┌───────────────────────┐  ┌────────────────────┐  │
│  │  Notebook UI          │  │  Chat Panel        │  │
│  │  Cell[], focused cell │  │  (existing)        │  │
│  │  CellEditor (CM)      │  │                    │  │
│  │  CellOutput           │  │  NotebookContext   │  │
│  │  Cell management      │  │  → tutor agent     │  │
│  └──────────┬────────────┘  └────────────────────┘  │
│             │                                       │
│     ┌───────┴───────┐                               │
│     │ ExecutionEngine│ (interface)                   │
│     │               │                               │
│     │  executePython(code) → PythonResult            │
│     │  executeSQL(sql) → QueryResult                 │
│     │  openTerminal() → TerminalStream | null        │
│     │  interrupt() → void                            │
│     │  isReady() → boolean                           │
│     └───────┬───────┘                               │
│             │                                       │
│     ┌───────┼────────────────┐                      │
│     ▼                        ▼                      │
│  ┌──────────────┐    ┌──────────────────┐           │
│  │ BrowserEngine│    │ RemoteEngine     │           │
│  │              │    │                  │           │
│  │ Pyodide (WW) │    │ Jupyter Kernel   │           │
│  │ sql.js       │    │ via WebSocket    │           │
│  │ terminal: ✗  │    │ terminal: ✓      │           │
│  └──────────────┘    └──────────────────┘           │
└─────────────────────────────────────────────────────┘
```

---

## The Interface

```typescript
interface ExecutionEngine {
  // Lifecycle
  init(): Promise<void>;
  isReady(): boolean;
  onReadyStateChange(cb: (ready: boolean) => void): void;
  reset(): Promise<void>;
  destroy(): void;

  // Execution
  executePython(code: string): Promise<PythonResult>;
  executeSQL(sql: string): Promise<QueryResult>;
  interrupt(): Promise<void>;  // kill running code

  // Terminal (server-only)
  supportsTerminal(): boolean;
  openTerminal?(): Promise<TerminalHandle>;

  // Capabilities
  capabilities(): {
    python: boolean;
    sql: boolean;
    terminal: boolean;
    fileSystem: boolean;
    pipInstall: boolean;
  };
}
```

**BrowserEngine** implements this with our existing Pyodide Web Worker + sql.js.
**RemoteEngine** implements this with Jupyter Kernel WebSocket + Jupyter Terminal API.

The notebook UI doesn't know or care which one is active.

---

## What We Build (Phased)

### Phase 1: In-Browser Notebook (Ship Now)

Everything from Option A, minus terminal. This is the PoC.

| Component | Source | Status |
|-----------|--------|--------|
| Python cells | @marimo-team/blocks + our Web Worker | New |
| SQL cells | Our existing sql-engine.ts | Existing |
| Markdown cells | react-markdown or similar | New (small) |
| Cell management (CRUD, reorder) | Custom Zustand + UI | New |
| LLM tutor context | Read from cell state | New (small) |
| Persistence | localStorage / IndexedDB | New (small) |
| Terminal | **Disabled** (greyed out, "requires server") | N/A |

**Effort:** ~13-19 days (same as Option A)

### Phase 2: Execution Engine Interface (Refactor)

Extract the execution layer into the `ExecutionEngine` interface so we can swap backends.

| Task | What changes |
|------|-------------|
| Define `ExecutionEngine` interface | New file |
| `BrowserEngine` wrapping Pyodide + sql.js | Thin wrapper around existing code |
| Engine selection logic | URL param `?engine=browser|remote` or auto-detect |
| Feature flags in UI | Disable terminal button when `!engine.supportsTerminal()` |

**Effort:** ~3-5 days

### Phase 3: JupyterHub Backend (When Ready)

Deploy JupyterHub. Implement `RemoteEngine`.

| Task | What changes |
|------|-------------|
| JupyterHub deployment | Infrastructure (Helm/K8s) |
| `RemoteEngine` class | WebSocket to Jupyter kernel |
| Terminal support | xterm.js + Jupyter Terminal WebSocket |
| `interrupt()` support | `POST /api/kernels/{id}/interrupt` |
| MCP bridge for tutor | Tutor reads via Jupyter API instead of React state |
| Auth flow | Learner's JupyterHub token passed to frontend |

**Effort:** ~15-25 days (same as Option B, but frontend is already done)

### Phase 4: Auto-Detection + Fallback

```
Learner opens workspace
  → Check: is JupyterHub available for this learner?
    → Yes: use RemoteEngine (full capabilities)
    → No: use BrowserEngine (Python + SQL only)
```

This could be based on:
- Learner's plan/tier (free = browser, paid = server)
- Course requirements (cyber course = server mandatory)
- Device detection (weak device → prefer server if available)
- Manual toggle in settings

**Effort:** ~2-3 days

---

## LLM Tutor Context — Both Backends

**In browser mode:** Tutor reads cells from React state (Jotai atoms + Zustand store). Same as current approach but with cell array instead of single editor content.

**In server mode:** Tutor reads cells from Jupyter Contents API (`GET /api/contents/notebook.ipynb`). More authoritative — includes execution output, cell metadata, kernel state.

**Unified context shape sent to tutor:**
```typescript
interface NotebookContext {
  cells: {
    id: string;
    type: "python" | "sql" | "markdown" | "terminal";
    content: string;
    output?: string;
    error?: string;
    isExecuting: boolean;
  }[];
  focused_cell_id: string;
  engine: "browser" | "remote";
  capabilities: { terminal: boolean; pip: boolean; filesystem: boolean };
}
```

The tutor agent doesn't need to know which backend is active. It sees cells and outputs either way. It just knows the capabilities differ.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Two execution backends = double the bugs | **Medium** | Strong interface contract. Shared test suite per engine. |
| Feature gap confusion ("why can't I use terminal?") | Medium | Clear UI messaging: "Terminal requires server connection" |
| Engine switch mid-session loses state | Medium | Serialize cell content before switch. Kernel state (variables) is lost — acceptable with warning. |
| Phase 1 ships without terminal (cyber blocked) | Medium | Cyber course waits for Phase 3. Other courses can ship. |
| Maintaining two backends long-term | Low-Medium | Browser engine is stable (Pyodide + sql.js). Minimal churn. |

---

## Cost Model

| Phase | Monthly Infra Cost | Users Served |
|-------|-------------------|-------------|
| Phase 1 (browser only) | $0 (static hosting) | Unlimited (client-side) |
| Phase 2 (interface refactor) | $0 | Same |
| Phase 3 (JupyterHub for server users) | $500-5,000 (scales with server users) | Server users only |
| Phase 4 (hybrid) | $500-5,000 | Unlimited (browser) + server tier |

**Key insight:** Not all 10,000 users need server-side compute. If 80% use browser mode (Python + SQL courses) and 20% need servers (cyber, advanced ML), you're provisioning for 2,000 server users, not 10,000.

At 2,000 server DAU: ~$1,500-2,500/month infrastructure.

---

## Effort Estimate (All Phases)

| Phase | Days | Ships |
|-------|------|-------|
| Phase 1: In-browser notebook | 13-19 | PoC with Python + SQL |
| Phase 2: Engine interface | 3-5 | Refactor (no new features) |
| Phase 3: JupyterHub backend | 15-25 | Terminal, real Python, pip |
| Phase 4: Auto-detection | 2-3 | Seamless tier switching |
| **Total** | **33-52 days** | Full hybrid |

But Phase 1 ships independently. You don't need Phase 3 to have a working product.

---

## When to Choose This Option

- You want to ship a PoC now but know you'll need servers later
- Different courses have different requirements (some need terminal, some don't)
- You want to offer free/paid tiers with different capabilities
- You want to derisk the JupyterHub investment by proving the product first
- You value the option to run without any infrastructure
