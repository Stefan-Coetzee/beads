# Option A: Custom Frontend with @marimo-team/blocks

> Build our own notebook UI using marimo-blocks for Python cells,
> our existing sql-engine for SQL, xterm.js for terminal, and our
> LLM tutor integrated natively via shared state.

---

## Summary

Use `@marimo-team/blocks` (v0.0.2, Apache-2.0) as the Python cell foundation. It provides `MarimoProvider`, `CellEditor`, `CellOutput`, `CellRunButton`, and `NotebookRunButton` — React components backed by Pyodide. We build everything else: SQL cells, terminal, cell management, LLM context, persistence, and the surrounding workspace UX.

**Everything runs in-browser. No server infrastructure.**

---

## What Blocks Gives Us (Free)

| Component | What it does |
|-----------|-------------|
| `MarimoProvider` | Loads Pyodide from CDN, installs dependencies, provides `usePyodide()` hook |
| `CellEditor` | CodeMirror + Python syntax, per-cell state via Jotai atoms, Cmd+Enter to run |
| `CellOutput` | MIME-type aware output rendering (text, error, JSON, custom renderers) |
| `CellRunButton` | Execute one cell, completion callback, disabled during execution |
| `NotebookRunButton` | Run all cells sequentially |
| `usePyodide()` | Access to `pyodide` instance, `runPython()`, `installPackage()`, `loading`, `error` |
| State management | Jotai atoms: `CodeAtoms` (per-cell code), `CellOutputAtoms` (per-cell output), `executingCellsAtom` |
| Custom renderers | Register MIME-type renderers (e.g., JSON viewer, matplotlib PNG) |
| Error boundary | Built in |

**LLM access to cells:** `CodeAtoms.get(cellId)` from any React component gives cell contents. `CellOutputAtoms.get(cellId)` gives outputs. This is simpler than our current prop-drilling approach.

---

## What We Build

### 1. Cell Management Layer

Blocks hard-codes cells in JSX. We need dynamic cell CRUD.

**Requirements:**
- `Cell` model: `{ id, type: "python"|"sql"|"markdown"|"terminal", order: number }`
- Add cell (above/below current)
- Delete cell (with confirmation if non-empty)
- Reorder cells (drag handle or move up/down buttons)
- Cell type selector (dropdown on new cell)
- Focus management (arrow keys between cells, focus new cell on create)

**State:** Zustand store with `cells: Cell[]`, `focusedCellId: string`. Python cell content lives in blocks' Jotai atoms; SQL/terminal cell content in our store.

**Effort:** Small-Medium (~2-3 days)

### 2. SQL Cell Type

Blocks only supports Python. SQL cells use our existing `sql-engine.ts`.

**Requirements:**
- `SqlCellEditor` — CodeMirror with SQL dialect (we have this: `SqlEditor`)
- `SqlCellOutput` — table rendering (we have this: `ResultsPanel`)
- Execution calls `executeQuery(sql)` from our existing engine
- SQL database loaded once, shared across all SQL cells
- Independent from Python cells (no shared kernel)

**State:** SQL cell content + results in our Zustand store, not in blocks' Jotai atoms.

**Effort:** Small (~1-2 days, mostly wiring existing components)

### 3. Terminal Cell Type (Cybersecurity)

No server-side shell available in-browser. Options:

**Option 3a: Simulated terminal (limited)**
- Command history, basic file operations
- Backed by a virtual filesystem (e.g., BrowserFS)
- Good for teaching `ls`, `cd`, `cat`, `grep` basics
- Cannot run real system commands

**Option 3b: WebContainer (stackblitz)**
- Node.js-based Linux-like environment in the browser
- Real filesystem, `npm`, basic shell commands
- No Python, no `apt`, no `sudo`
- 10+ MB download

**Option 3c: Defer terminal to server-side (Option B)**
- Don't include terminal in the in-browser version
- Terminal only available when connected to JupyterHub
- Mark terminal cells as "requires server connection"

**Recommendation:** Option 3c. A simulated terminal is a poor learning experience for cyber. Defer to server-side.

**Effort:** 0 (deferred) or Medium (~1 week for simulated)

### 4. LLM Tutor Context Integration

The tutor needs to see all cells, their outputs, and which cell the learner is focused on.

**Requirements:**
- Build `NotebookContext` from cell state:
  ```ts
  {
    cells: [
      { id, type, content, output, isExecuting },
      ...
    ],
    focused_cell_id: string,
    workspace_type: "notebook"
  }
  ```
- Send as part of chat `WorkspaceContext` to backend
- Backend agent receives full notebook state per chat message
- Tutor can reference cells by position ("look at cell 3") or content

**Reading Python cells:** `CodeAtoms.get(cellId)` + `CellOutputAtoms.get(cellId)` (from blocks' Jotai store)
**Reading SQL cells:** From our Zustand store
**Reading focus:** From our Zustand store `focusedCellId`

**Effort:** Small (~1-2 days)

### 5. Execution Timeout / Kill

Blocks runs Pyodide on the **main thread**. No Web Worker. Infinite loops freeze the tab.

**Options:**
- **Swap blocks' MarimoProvider for our Web Worker engine**: Keep blocks' `CellEditor` and `CellOutput` but replace execution with our `executePython()` via Web Worker. This means reimplementing `useCellExecution` to call our engine instead of blocks' `runPython()`.
- **Accept the freeze risk**: For a PoC, learners can refresh the tab. Document the limitation.
- **Fork blocks and add Worker support**: Blocks is 5 commits and <1,000 lines. Forking is low risk.

**Recommendation:** Swap execution to our Web Worker engine. Keep blocks for the UI atoms + CodeMirror setup. This gives us the best of both: blocks' cell state management + our timeout/kill capability.

**Effort:** Medium (~2-3 days)

### 6. Persistence

Blocks' Jotai atoms are in-memory only. Page refresh loses everything.

**Requirements:**
- Serialize `cells[]` + their content to localStorage or IndexedDB
- Restore on page load
- Schema versioning (already have pattern in workspace store)
- Optional: save to backend API per learner per project

**Approach:** Subscribe to Jotai atom changes, debounce-write to localStorage. On mount, hydrate atoms from storage.

**Effort:** Small (~1 day)

### 7. Notebook Chrome (UI Shell)

**Requirements:**
- Vertical scrollable cell list (left pane)
- Chat panel (right pane, existing)
- Toolbar: Run All, Clear All Outputs, Add Cell, Reset Environment
- Cell toolbar per cell: Run, Delete, Move Up/Down, Type selector
- Keyboard shortcuts: Cmd+Enter (run cell), Shift+Enter (run and advance), Escape (deselect cell), A/B (add cell above/below in command mode)
- Markdown cell rendering (view mode → edit on click)

**Effort:** Medium (~3-5 days)

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `@marimo-team/blocks` abandoned (v0.0.2, 5 commits) | **High** | Fork early. It's <1,000 lines of code. We can maintain it. |
| Main-thread Pyodide freezes on infinite loops | High | Swap execution to our Web Worker |
| No terminal support in browser | Medium | Defer to server-side option |
| Two state systems (Jotai for Python cells, Zustand for everything else) | Medium | Acceptable complexity. Bridge via subscription. |
| Pyodide download (~15 MB) slow for learners | Low | Already solved — show loading progress |
| Blocks API breaks on update | Low | Pin version. It's 5 commits, unlikely to change. |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│  Notebook Page                                      │
│                                                     │
│  ┌───────────────────────┐  ┌────────────────────┐  │
│  │  Cell List (scroll)   │  │  Chat Panel        │  │
│  │                       │  │  (existing)        │  │
│  │  ┌─ Python Cell ────┐ │  │                    │  │
│  │  │ CellEditor (blks)│ │  │  Reads cells via   │  │
│  │  │ CellOutput (blks)│ │  │  NotebookContext   │  │
│  │  │ CellRunButton    │ │  │                    │  │
│  │  └──────────────────┘ │  │                    │  │
│  │                       │  │                    │  │
│  │  ┌─ SQL Cell ───────┐ │  │                    │  │
│  │  │ SqlEditor (ours) │ │  │                    │  │
│  │  │ ResultsPanel     │ │  │                    │  │
│  │  │ Run button       │ │  │                    │  │
│  │  └──────────────────┘ │  │                    │  │
│  │                       │  │                    │  │
│  │  ┌─ Markdown Cell ──┐ │  │                    │  │
│  │  │ Rendered / Edit  │ │  │                    │  │
│  │  └──────────────────┘ │  │                    │  │
│  │                       │  │                    │  │
│  │  [+ Add Cell]         │  │                    │  │
│  └───────────────────────┘  └────────────────────┘  │
│                                                     │
│  MarimoProvider (Pyodide)    Our Zustand Store       │
│  Jotai atoms (Python cells)  (SQL cells, UI, chat)   │
└─────────────────────────────────────────────────────┘
```

---

## Dependency List

| Package | Version | Size | Purpose |
|---------|---------|------|---------|
| `@marimo-team/blocks` | ^0.0.2 | ~TBD | Python cell components |
| `jotai` | ^2.11 | ~8 KB | Peer dep of blocks |
| `pyodide` | ^0.27 | ~15 MB (CDN) | Python WASM runtime |
| `@uiw/react-codemirror` | existing | existing | Already in project |
| `@codemirror/lang-python` | ^6.1 | ~50 KB | Peer dep of blocks |
| `xterm` | — | — | Future: terminal |
| `sql.js` | existing | existing | Already in project |

---

## Effort Estimate

| Work Item | Days | Depends On |
|-----------|------|-----------|
| Cell management (CRUD, reorder, focus) | 2-3 | — |
| SQL cell type (wire existing components) | 1-2 | Cell management |
| Swap Python execution to Web Worker | 2-3 | — |
| LLM context integration | 1-2 | Cell management |
| Persistence (localStorage) | 1 | Cell management |
| Notebook chrome (toolbar, keyboard shortcuts) | 3-5 | Cell management |
| Markdown cell type | 1 | Cell management |
| Integration testing + polish | 2-3 | All above |
| **Total** | **~13-19 days** | |

---

## When to Choose This Option

- You want to ship fast with zero infrastructure
- Your learners have decent devices (can handle ~15 MB Pyodide download)
- Terminal/cyber exercises can wait or use a separate tool
- You're comfortable maintaining a fork of a v0.0.2 library
- Offline capability matters
