# Notebook Workspace — Build vs Buy

> Can we pull in an existing notebook, or do we build one?
> Critical requirement: the LLM tutor must be able to read cell contents.

---

## The Landscape

There are roughly 4 tiers of options, from heaviest to lightest:

### Tier 1: Full notebook apps (iframe embed)

**JupyterLite** and **Marimo** are complete notebook applications that run 100% in-browser via Pyodide. Both are actively maintained (4.8k and 19.2k GitHub stars respectively). You embed them in an iframe.

**Problem:** iframe isolation makes it hard for our LLM to read cell contents. JupyterLite has an early-stage `jupyter-iframe-commands` extension (9 stars, "early development stage") that bridges postMessage, but fine-grained cell read/write isn't mature. Marimo has no host-page JavaScript API at all — there's an open discussion requesting React component embedding, but it doesn't exist yet.

**Verdict:** Too opaque for our use case. The whole point is the tutor seeing what the learner writes.

### Tier 2: React-native Jupyter components

**@datalayer/jupyter-react** (449 stars, MIT, active) wraps JupyterLab internals in React components. It provides `<Notebook>`, `<Cell>`, `<Console>` components that work natively in React. Set `lite={true}` and it uses Pyodide — no server kernel. Full programmatic cell read/write.

**Problem:** It bundles all of JupyterLab + Lumino under the hood. Expect 5–15+ MB of JS bundles on top of Pyodide's ~15 MB WASM. That's 20–30 MB before any Python packages. For learners on slow connections or small devices, this is brutal.

**@marimo-team/blocks** (Apache-2.0) provides lightweight React components (`CellEditor`, `CellOutput`, `CellRunButton`) backed by Marimo + Pyodide. This is exactly what we'd want — but it's at **v0.0.2**, published 10 months ago with unclear activity.

**Verdict:** `@datalayer/jupyter-react` works but is extremely heavy. `@marimo-team/blocks` is the right shape but too immature to bet on.

### Tier 3: Execution hooks (bring your own UI)

**thebe-react + thebe-lite** (434 stars, BSD-3) gives you React hooks for executing code against a JupyterLite/Pyodide kernel. You build the notebook UI yourself, Thebe handles the execution engine. You own the cell state, so reading/writing cells for the LLM is trivial.

**react-py** (295 stars, MIT) is simpler — a `usePython` hook that runs code in a Pyodide Web Worker. No notebook UI, just execution.

**Verdict:** Thebe is interesting but still loads JupyterLite under the hood for the kernel. react-py is essentially what we already built with our Web Worker.

### Tier 4: Custom build (CodeMirror + our existing Pyodide worker)

We already have:
- CodeMirror editors (SqlEditor, PythonEditor)
- Pyodide in a Web Worker with timeout/kill
- Results panels for stdout, stderr, tables
- A Zustand store for state management

A notebook is: an ordered list of `{ id, type, content, result }` cells, each rendered as a CodeMirror editor + inline result. Execution calls our existing `executePython(code)` or `executeQuery(sql)`.

**Verdict:** Lightest option. Total control over LLM integration. We maintain the notebook UX ourselves.

---

## Comparison Matrix

| Option | LLM can read cells | Bundle overhead | React native | Maturity | Maintenance burden |
|--------|-------------------|----------------|-------------|----------|-------------------|
| JupyterLite (iframe) | Hard (postMessage) | ~25 MB+ | No (iframe) | Production | Low (theirs) |
| Marimo (iframe) | No JS API | ~25 MB+ | No (iframe) | Production | Low (theirs) |
| @datalayer/jupyter-react | Yes (full API) | ~20-30 MB total | Yes | Usable | Low (theirs) |
| @marimo-team/blocks | Yes (React props) | Unknown | Yes | v0.0.2 | Risk (abandoned?) |
| thebe-react + thebe-lite | Yes (you own UI) | ~15-20 MB | Yes (hooks) | Moderate | Medium (shared) |
| **Custom (ours)** | **Yes (trivially)** | **~15 MB (Pyodide only)** | **Yes** | **We control** | **Higher (ours)** |

---

## Recommendation

**Build it ourselves (Tier 4), but keep it minimal.**

Rationale:

1. **LLM access is the hard requirement.** Every iframe-based solution (JupyterLite, Marimo) makes this painful. The React-native options either bundle too much (@datalayer) or are too immature (@marimo-team/blocks).

2. **We already have 80% of the pieces.** Our Pyodide Web Worker, CodeMirror editors, results panels, and Zustand store are all cell-agnostic. The notebook is a `Cell[]` array where each cell calls existing engine functions.

3. **Bundle size matters.** Our learners are students, potentially on university WiFi or mobile. Pyodide is already ~15 MB. Adding another 10-15 MB of JupyterLab internals doubles the download for marginal UX gain.

4. **We don't need full Jupyter.** No IPython magics, no ipywidgets, no kernel interrupts, no nbformat compatibility. We need: ordered cells, run one/run all, inline results, and the tutor can see everything.

5. **The notebook UX is simple.** It's a vertical list of editors with run buttons and inline output. CodeMirror handles the editing. The hard part (Pyodide execution, timeout handling, error parsing) is already solved.

### What "custom" looks like

```
Cell model:  { id, type: "python"|"sql", content: string, result: PythonResult|QueryResult|null, isExecuting: boolean }
Store:       cells: Cell[], focusedCellId: string
Layout:      Vertical scroll of <CellEditor> + <CellResult> pairs
Execution:   Cell.content → executePython() or executeQuery() → Cell.result
LLM context: cells.map(c => ({ type, content, result })) → WorkspaceContext
```

Estimated effort: ~1 week for a working notebook, another week for polish (drag-reorder, add/delete cells, keyboard nav between cells, "Run All").

### When to reconsider

If **@marimo-team/blocks** reaches v1.0 with active maintenance, it becomes the obvious choice — it's exactly the right abstraction (React components for a Pyodide notebook). Worth checking back quarterly.

If we need **.ipynb import/export**, the custom approach gets harder. At that point, `thebe-react` with its Jupyter kernel compatibility might be worth the bundle cost.

---

## References

- [JupyterLite](https://github.com/jupyterlite/jupyterlite) — 4.8k stars, BSD-3, official Jupyter project
- [jupyter-iframe-commands](https://github.com/TileDB-Inc/jupyter-iframe-commands) — 9 stars, early stage
- [Marimo](https://github.com/marimo-team/marimo) — 19.2k stars, Apache-2.0, very active
- [Marimo React embedding discussion](https://github.com/marimo-team/marimo/discussions/962)
- [@datalayer/jupyter-react](https://github.com/datalayer/jupyter-ui) — 449 stars, MIT, active
- [@marimo-team/blocks](https://www.npmjs.com/package/@marimo-team/blocks) — v0.0.2, Apache-2.0
- [Thebe](https://github.com/jupyter-book/thebe) — 434 stars, BSD-3
- [react-py](https://github.com/elilambnz/react-py) — 295 stars, MIT
- [Starboard Notebook](https://github.com/gzuidhof/starboard-notebook) — 1.3k stars, MPL-2.0, inactive
- [Pyodide related projects](https://pyodide.org/en/stable/project/related-projects.html)
