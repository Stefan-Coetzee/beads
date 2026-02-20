# Notebook Workspace — Feasibility Assessment

> How far off is a Jupyter-style notebook, and how clean is the current setup?

---

## Current Architecture (Single-Editor Model)

The workspace is a **2-pane layout**: editor left, chat right, with a results panel below the editor. Each workspace type (SQL, Python) has its own editor component, results panel, and execution engine. State flows through a flat Zustand store.

```
┌─────────────────────────────┬──────────────────┐
│  Editor (single buffer)     │                  │
│  ─────────────────────────  │   Chat Panel     │
│  Results (latest execution) │                  │
└─────────────────────────────┴──────────────────┘
```

Everything assumes **one editor string → one execution → one result**.

---

## What's Clean

**Engines are cell-agnostic.** `executePython(code)` and `executeQuery(sql)` take a string and return a result. They don't know or care whether the input is from a single editor or cell #7. No refactoring needed here.

**Components are presentation-only.** `SqlEditor`, `PythonEditor`, `ResultsPanel`, `PythonResultsPanel` are all pure props-in, callbacks-out. No internal state management, no side effects. They could be wrapped inside a `<Cell>` component without touching their internals.

**Store is flat and simple.** Zustand store has no deeply nested structures. Migrating from `pythonContent: string` to `cells: Cell[]` is a schema version bump, not an architectural change.

**Chat context is a plain object.** The `WorkspaceContext` sent to the backend is `{ editor_content, results, workspace_type }`. Extending this to `{ cells: CellContext[], focused_cell_id }` is straightforward on both frontend and backend.

**Execution flow is synchronous-feeling.** Even though Python runs in a Web Worker, the call pattern is `const result = await executePython(code)`. A notebook just calls this in a loop.

---

## What Needs Work

### Store Schema (Medium)

Current store tracks two parallel strings:
```
sqlContent: string
pythonContent: string
queryResults: QueryResult | null
pythonResults: PythonResult | null
```

Notebook needs:
```
cells: Cell[]          // ordered list
focusedCellId: string  // which cell is active
```

Where `Cell` is roughly `{ id, type, content, result, isExecuting }`. This is a migration, not a rewrite — the persistence layer already handles schema version bumps.

### Page Layout (Medium)

Current layout is a horizontal `PanelGroup` split. A notebook is a **vertical scroll** of cells, each with its own editor + inline result. The `react-resizable-panels` setup stays for the editor-vs-chat split, but the left panel's internals change from "editor above, results below" to "scrollable cell list."

### Execution Tracking (Medium)

Currently there's a single `isExecuting` boolean and a single execution timer. A notebook needs per-cell execution state. The timer warning ("stopping in Xs") would attach to the active cell, not a global overlay.

### Chat Context (Low-Medium)

Chat currently receives the full editor content as a single string. For a notebook, it would need:
- All cells (or at least the focused cell + its neighbours)
- Which cell the learner is working on
- Execution history (not just the latest result)

The backend API already accepts a `WorkspaceContext` object — extending it is additive.

### Task-to-Cell Binding (Low)

Currently a task maps to a workspace. In a notebook, a task might map to a specific cell or cell range. The `TaskDetailDrawer` "Open in Workspace" link would need a cell anchor. This is a UX decision more than a technical one.

---

## What's Free

- **Mixed-language cells** — the engines are independent. A notebook could have SQL cells and Python cells interleaved. Each cell just calls the appropriate engine.
- **Cell reordering** — since cells are an array with IDs, drag-to-reorder is just array manipulation.
- **Selective execution** — "Run this cell" is already how the engines work. "Run all" is a loop. "Run above" is a filtered loop.
- **Per-cell results** — each `Cell` owns its `result`. No shared result slot to fight over.
- **Web Worker timeout** — `worker.terminate()` kills infinite loops regardless of which cell triggered them. The re-init cost (reloading Pyodide ~15 MB) is the same.

---

## Rough Effort Estimate

| Area | Effort | Notes |
|------|--------|-------|
| `Cell` data model + store migration | Small | New type, array in store, version bump |
| `NotebookLayout` component | Medium | Vertical scroll of `<Cell>` components, each with editor + result |
| `CellEditor` wrapper | Small | Wraps existing `PythonEditor`/`SqlEditor` with cell ID + controls |
| Per-cell execution state | Small | Move `isExecuting` + timer into cell object |
| "Run All" / "Run Above" | Small | Loop over cells calling existing engine functions |
| Chat context for multi-cell | Medium | Send cell array, track focused cell |
| Backend context handling | Low | Already receives `WorkspaceContext`, extend schema |
| Task-to-cell binding | Low | Optional — can defer |
| Cell persistence (localStorage) | Small | Already persisting editor content, extend to cell array |
| **Total** | **~1-2 weeks** | Assuming the current single-editor mode stays as a fallback |

---

## Biggest Risk

**Pyodide shared state across cells.** In Jupyter, cells share a kernel — variables defined in cell 1 are available in cell 2. Our Web Worker already preserves Python globals between `executePython()` calls (the worker stays alive). So this works naturally.

But: if the worker gets terminated (infinite loop timeout), **all cell state is lost**. Jupyter handles this with a "kernel died, restart?" dialog. We'd need the same UX.

SQL doesn't have this problem — each query is stateless against the database.

---

## Recommendation

The current setup is **clean enough** that a notebook is an extension, not a rewrite. The key architectural decisions (engines as functions, store as flat state, components as presentation) all point in the right direction. The main work is UI (vertical cell layout) and state shape (array of cells), not plumbing.

Start with Python-only notebook, since SQL cells are inherently single-query and benefit less from the notebook model. Add SQL cells later if needed.
