# Option B: JupyterHub + MCP Tutor

> Each learner gets an isolated Jupyter server with real Python, terminal,
> and SQL. Our LLM tutor joins as a collaborator via MCP bridge.
> We build the curriculum/task layer; Jupyter handles the compute.

---

## Summary

Deploy JupyterHub to provision per-learner Jupyter servers. Our backend registers as a JupyterHub service with a scoped API token. The LLM tutor connects to each learner's session via Jupyter's REST API (read/write notebooks), Kernel WebSocket (execute code), Terminal API (shell access), and optionally RTC/CRDT (real-time collaboration). Our React frontend either embeds JupyterLab in an iframe or replaces it entirely with our own UI talking to Jupyter APIs.

**All execution happens server-side. Browser is a thin client.**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Our Platform                                                │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │ Next.js App │   │ LTT API      │   │ LLM Tutor Agent  │  │
│  │ (frontend)  │   │ (FastAPI)    │   │ (LangGraph)      │  │
│  │             │   │              │   │                  │  │
│  │ Chat panel  │   │ Tasks, prog. │   │ Reads cells via  │  │
│  │ Task drawer │   │ Submissions  │   │ Jupyter API      │  │
│  │ Curriculum  │   │ Validations  │   │                  │  │
│  └──────┬──────┘   └──────────────┘   └────────┬─────────┘  │
│         │                                      │             │
│         │         ┌────────────────────┐        │             │
│         └────────→│  JupyterHub        │←───────┘             │
│                   │                    │                      │
│                   │  Auth (LTI/OAuth)  │                      │
│                   │  Spawner (K8s/Docker)                     │
│                   │  Service: ltt-tutor │                     │
│                   └────────┬───────────┘                      │
│                            │                                 │
│              ┌─────────────┼─────────────┐                   │
│              ▼             ▼             ▼                   │
│     ┌──────────────┐ ┌──────────┐ ┌──────────┐             │
│     │ /user/lnr-47 │ │ /user/48 │ │ /user/49 │  ...×10,000 │
│     │              │ │          │ │          │             │
│     │ JupyterLab   │ │          │ │          │             │
│     │ Python kernel│ │          │ │          │             │
│     │ Terminal PTY │ │          │ │          │             │
│     │ Files (NFS)  │ │          │ │          │             │
│     └──────────────┘ └──────────┘ └──────────┘             │
└──────────────────────────────────────────────────────────────┘
```

---

## What Jupyter Gives Us (Free)

| Capability | How | API |
|-----------|-----|-----|
| Python notebook | JupyterLab native | Built-in |
| SQL execution | `ipython-sql` magic (`%sql SELECT ...`) or SQLite kernel | Kernel extension |
| Terminal (cyber) | Jupyter Terminal API | `POST /api/terminals`, WebSocket |
| File editor | JupyterLab built-in | Contents API |
| Package management | `pip install` in real environment | Kernel execution |
| Real filesystem | Container with persistent NFS home dir | Contents API |
| Multi-language | Install any Jupyter kernel (R, Julia, Bash) | Kernel specs |
| Infinite loop kill | `POST /api/kernels/{id}/interrupt` | REST |
| Kernel restart | `POST /api/kernels/{id}/restart` | REST |
| Per-learner isolation | JupyterHub spawner (Docker/K8s) | Built-in |
| Authentication | LTI (from LMS), OAuth, LDAP | JupyterHub auth |

---

## What We Build

### 1. JupyterHub Deployment + Configuration

**Requirements:**
- Kubernetes cluster (EKS/GKE/AKS) or Docker Swarm
- JupyterHub Helm chart (zero-to-jupyterhub)
- Spawner config: per-learner containers with resource limits
- Authentication: LTI for LMS integration, or OAuth for standalone
- Idle culling: 20-minute timeout, 4-hour max lifetime
- Node autoscaling: scale to zero overnight
- Shared NFS storage for learner home directories
- Pre-built container image with course packages

**Key configuration:**
```yaml
# values.yaml (Helm)
singleuser:
  image:
    name: our-registry/ltt-learner
    tag: latest
  memory:
    guarantee: 512M
    limit: 1G
  cpu:
    guarantee: 0.1
    limit: 0.5
  storage:
    capacity: 2Gi
    dynamic:
      storageClass: nfs-client

hub:
  services:
    ltt-tutor:
      apiToken: <generated>
      oauth_roles:
        - tutor-role

  loadRoles:
    tutor-role:
      scopes:
        - access:servers    # proxy to user servers
        - read:users:activity
```

**Effort:** Medium-Large (~1-2 weeks for initial deployment, ongoing ops)

### 2. LTT Tutor ↔ Jupyter Integration

Our tutor backend needs to read/write learner notebooks and execute code.

**Requirements:**

**Reading notebooks (what the learner wrote):**
```
GET /user/{learner}/api/contents/exercise.ipynb
Authorization: token {service_token}

→ Returns full notebook JSON:
  { cells: [ { cell_type, source, outputs, ... }, ... ] }
```

**Executing code (diagnostic checks, running learner's code):**
```
WS /user/{learner}/api/kernels/{kernel_id}/channels

→ Send: { msg_type: "execute_request", content: { code: "print(x)" } }
← Recv: { msg_type: "stream", content: { text: "42\n" } }
← Recv: { msg_type: "execute_reply", content: { status: "ok" } }
```

**Reading terminal output (cyber exercises):**
```
GET /user/{learner}/api/terminals → list terminals
WS /user/{learner}/terminals/websocket/{name} → bidirectional PTY
```

**Writing to notebooks (tutor suggestions):**
```
GET notebook → modify cells[] → PUT notebook
```

**Implementation:**
- `JupyterClient` class in our backend wrapping REST + WebSocket
- Called by the LLM agent as tools: `read_notebook`, `execute_in_kernel`, `read_terminal`
- Scoped per-request to specific learner via URL path

**Effort:** Medium (~1-2 weeks)

### 3. MCP Bridge (Alternative to Custom Integration)

Instead of building the Jupyter client ourselves, use existing MCP tools.

**Options (all available now):**

| Tool | What it does | Effort to integrate |
|------|-------------|-------------------|
| `jupyter-ai-agents` (Datalayer) | Full agent framework — RTC + kernel + Pydantic AI. Uses Claude. | Install + configure. May conflict with our LangGraph agent. |
| `mcp-jupyter` | Lightweight MCP server: `read_cell`, `execute_cell`, `insert_cell` | Add as MCP server to our agent |
| `jupyter-collaboration-mcp` | Joins Y.js CRDT layer — real-time cell editing as collaborator | Add as MCP server. Learner sees AI cursor. |

**Recommendation:** Start with `mcp-jupyter` for simplicity. It gives us `read_cell`, `execute_cell`, `list_cells` as MCP tools our LangGraph agent can call. Upgrade to the CRDT bridge later if real-time collaboration matters.

**Effort:** Small (~2-3 days to wire MCP server into our agent)

### 4. Frontend Integration

Two sub-options:

**4a: Embed JupyterLab in iframe (simplest)**
- Our Next.js app wraps JupyterLab in an iframe at `/user/{learner}/`
- Chat panel is our React component alongside the iframe
- Tutor reads cells via API (not from the iframe DOM)
- Learner gets full JupyterLab UX (extensions, keybindings, etc.)

**Pros:** Zero frontend work on the notebook itself.
**Cons:** Two UIs (our app + JupyterLab). No deep integration. Feels like two products stitched together.

**4b: Our React UI + Jupyter APIs (richer but more work)**
- Our React app replaces JupyterLab entirely
- CodeMirror editors talk to Jupyter kernels via WebSocket
- Our results panels render kernel output
- Our terminal component uses xterm.js + Jupyter Terminal WebSocket
- Unified UX — one app, one design system

**Pros:** Seamless UX. Full control over the learning experience.
**Cons:** Significant frontend work. We rebuild what JupyterLab already does.

**Recommendation:** Start with 4a (iframe) for PoC. Migrate to 4b later if the stitched UX is unacceptable.

**Effort:** 4a: Small (~2-3 days). 4b: Large (~3-4 weeks).

### 5. Curriculum Delivery via Notebooks

Pre-populate learner notebooks with task instructions, starter code, and acceptance criteria.

**Requirements:**
- Template notebooks per task (stored in our content system)
- On task start: copy template to learner's home dir via Contents API
- Template includes markdown cells (instructions), empty code cells (workspace), and hidden test cells (validation)
- Tutor knows which cells map to which tasks (metadata in cell tags)

**Effort:** Medium (~1 week)

### 6. Validation via Kernel Execution

Replace our current SimpleValidator with real code execution.

**Requirements:**
- Learner submits (clicks "Check" or tutor triggers)
- Backend executes test code in learner's kernel
- Parse output for pass/fail
- Update `learner_task_progress` accordingly
- Handle edge cases: kernel died, timeout, import errors

**Effort:** Medium (~1 week)

---

## SQL in JupyterHub

Three approaches, none require SQL in the notebook itself:

**Approach A: `ipython-sql` magic**
```python
%load_ext sql
%sql sqlite:///maji_ndogo.db
%sql SELECT * FROM visits LIMIT 10;
```
Learner writes SQL in a Python cell prefixed with `%sql`. Results render as tables. Good enough for learning.

**Approach B: Dedicated SQL kernel**
Install `xeus-sql` or `jupysql` kernel. Learner gets a native SQL notebook. No Python wrapping.

**Approach C: Separate SQL editor in our UI**
Keep our existing SQL workspace as a separate view. Don't put SQL in the notebook at all. The notebook is for Python; SQL has its own editor.

**Recommendation:** Approach C for now. SQL and notebook are separate workspace types, as originally designed. Add `%sql` magic as a convenience later.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Infrastructure cost (~$5-7K/month at 10K users) | **High** | Start with smaller scale. Use spot instances + autoscaling. |
| Ops complexity (Kubernetes, networking, storage) | **High** | Use 2i2c managed service ($1.5K/month ops fee) |
| Learner server cold start (2-5 min first login) | Medium | Image pre-pulling, placeholder pods |
| Kernel dies mid-session (OOM, crash) | Medium | Auto-restart, persistent storage preserves files |
| MCP tools are new/unstable | Medium | Fall back to direct REST/WebSocket integration |
| JupyterLab UX doesn't match our design system | Medium | iframe for PoC, custom UI later |
| Network dependency (no offline) | Medium | Acceptable for server-side option |
| Security (learner has shell access in container) | Medium | Resource limits, network policies, read-only base image |

---

## Effort Estimate

| Work Item | Days | Depends On |
|-----------|------|-----------|
| JupyterHub deployment (Helm + K8s) | 5-7 | Infrastructure |
| JupyterHub config (auth, spawner, culling) | 3-5 | Deployment |
| Container image (packages, course material) | 2-3 | — |
| MCP bridge to tutor agent | 2-3 | Deployment |
| Frontend iframe integration | 2-3 | Deployment |
| Curriculum notebook templates | 3-5 | — |
| Validation via kernel execution | 3-5 | MCP bridge |
| Monitoring + alerting | 2-3 | Deployment |
| **Total** | **~22-34 days** | |
| (With 2i2c managed: subtract ~8 days for deployment/ops) | **~14-26 days** | |

---

## When to Choose This Option

- You have 100+ learners and need real compute isolation
- Terminal/cyber exercises are a core requirement
- Learners need real Python (C extensions, pip install, filesystem)
- You can absorb ~$5-7K/month infrastructure cost
- You want the LLM tutor to be a true collaborator in the learner's environment
- You have (or can hire) DevOps capacity, or use 2i2c
