# List of features important for PoC. 

1. Login or LTI spin up. We have to track their email + progress and final grade. 
2. Response should be streamed
3. We should catch Python errors in browser to avoid a next js error
4. We can probably truncate conversation at the task level - 1 task, 1 context
5. Need context window compression
6. Needs avatar & design
7. Chat needs history reload
8. Safe and simple deployment - Mike about simple auth, or cookie read? 
9. Comprehensive tests. 
10. Ensure default comments are there, and ensure those comments are scrubbed. Or should be shown somehow as external. 
11. Add explainer focus - here is project, code, etc. 
12. Log user data to simple gradebook. 
13. Set up policy - if fail, what then
14. On first load, intro should be better, and ideally contextual to the project (first_message kinda thing)

---

## Workspace Engines - Architecture Notes

### SQL Engine (sql-engine.ts)
- Uses **sql.js** (SQLite compiled to WebAssembly, runs in browser)
- Database lives entirely **in-memory** (~10-30 MB depending on dataset)
- First load: downloads SQL file (~10 MB), executes all statements, caches built binary in **IndexedDB**
- Subsequent loads: restores from IndexedDB cache (~100ms vs ~3-5s)
- `Reset DB` button bypasses cache and re-downloads from source
- **No infinite loop protection** - runs on main thread, will freeze the tab
- Progress bar shows download + initialization progress

### Python Engine (python-engine.ts)
- Uses **Pyodide** (CPython compiled to WebAssembly, runs in browser)
- Initial download: ~15 MB WASM core from CDN
- Packages loaded on demand (numpy ~7 MB, pandas ~15 MB, etc.)
- Runtime memory: ~50-150 MB depending on loaded packages
- Auto-detects `import` statements and loads packages before execution
- **No infinite loop protection** - will freeze the tab
- stdout/stderr captured via Python's `StringIO`

### Known Limitations
- **Infinite loops**: Both engines run on main thread. Need Web Workers for kill support.
- **Small devices**: Pyodide is heavy (15 MB + packages). Phones with <2 GB RAM may OOM.
- **No persistence**: Python state resets on refresh. SQL data persists via IndexedDB cache.

### Remote Execution Fallback
Both engines share a common `ExecutionResult` interface (success/error/output). Swapping to
remote execution requires:
1. Backend endpoint that runs code in sandboxed container (Docker/Jupyter kernel)
2. Replace `executePython()` / `executeQuery()` calls with API requests
3. Interface swap is trivial; sandboxed backend is the real work