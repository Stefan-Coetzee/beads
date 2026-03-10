# Learner Memory System

How the tutor agent remembers things about learners across sessions.

---

## Problem

Every conversation with the tutor starts from zero. The agent doesn't know the learner's name, what they struggled with last time, or how they prefer to learn. This makes the tutoring experience feel impersonal and forces learners to re-establish context.

## Solution

Persistent memory stored in PostgreSQL via LangGraph's `AsyncPostgresStore`. The agent loads memories into its system prompt at the start of each session and can store new observations as it teaches.

## Two Memory Scopes

### 1. Global (cross-project)

Who is this learner — structured profile + unstructured facts.

```
Namespace: (learner_id, "profile")    key="main"     → LearnerProfile
Namespace: (learner_id, "memories")   key=UUID        → MemoryEntry
```

Examples:
- Profile: name="Alice", programming_experience="beginner", learning_style="visual"
- Memory: "Prefers step-by-step explanations with examples"

### 2. Project-specific

Observations scoped to a particular project, shared across versions.

```
Namespace: (learner_id, project_slug, "memories")   key=UUID → MemoryEntry
```

Uses `project_slug` (stable `"maji-ndogo-part1-v3"`) not the internal ID (`proj-4aa7`), so memories persist when a project is re-ingested.

Examples:
- "Struggled with WHERE + AND combinations"
- "Understood LIKE quickly after wildcard analogy"

---

## Data Flow

```
Session start
    │
    ▼
create_agent(learner_id, project_id, store=...)
    │
    ├── load project task → resolve project_slug
    ├── LearnerMemory(store, learner_id, project_slug)
    │     ├── get_profile()
    │     ├── get_global_memories()
    │     └── get_project_memories()
    │
    ├── format_memories_for_prompt() → <learner_memory> block
    │
    └── build_system_prompt(...) + memory block
          │
          ▼
    Agent starts with full context + learner memory in prompt
```

During the session, the agent can call two tools:

```
store_memory(text, context, scope)       → writes to global or project namespace
update_learner_profile(name, style, ...) → patches the structured profile
```

Next session, those memories appear in the system prompt automatically.

---

## Key Files

| File | Role |
|------|------|
| `services/agent-tutor/src/agent/memory/schemas.py` | `LearnerProfile`, `MemoryEntry` models |
| `services/agent-tutor/src/agent/memory/namespaces.py` | Namespace tuple constructors |
| `services/agent-tutor/src/agent/memory/store.py` | `LearnerMemory` — CRUD wrapper around the store |
| `services/agent-tutor/src/agent/memory/reader.py` | `format_memories_for_prompt()` — formats for system prompt |
| `services/agent-tutor/src/agent/tools.py` | `_create_memory_tools()` — `store_memory` + `update_learner_profile` |
| `services/agent-tutor/src/agent/prompts.py` | `MEMORY_INSTRUCTIONS` — when/how to use memory tools |
| `services/agent-tutor/src/agent/graph.py` | `create_agent()` — loads memories, builds prompt |
| `services/api-server/src/api/agents.py` | `init_store()` / `get_store()` — store lifecycle |
| `services/api-server/src/api/inspector_routes.py` | `GET /api/v1/debug/memory/{learner_id}` — debug endpoint |

---

## Store Initialization

```
lifespan startup
    │
    ├── init_database()           — main DB (asyncpg)
    ├── init_checkpointer()       — conversation history (psycopg)
    └── init_store()              — learner memory (psycopg, separate pool)
```

Both checkpointer and store use `LTT_CHECKPOINT_DATABASE_URL`. Each gets its own connection pool. In local dev (no checkpoint DB), both fall back to in-memory implementations.

---

## Profile Patch Semantics

When the agent calls `update_learner_profile`, only provided fields are updated. List fields (`strengths`, `areas_for_growth`, `interests`) use **append + deduplicate** rather than replacement:

```python
# First call
update_learner_profile(strengths=["pattern recognition"])
# Profile: strengths=["pattern recognition"]

# Second call
update_learner_profile(strengths=["curiosity"])
# Profile: strengths=["pattern recognition", "curiosity"]  ← appended, not replaced
```

This is safer for LLM-driven updates where the agent might not know the full existing list.

---

## Prompt Format

When memories exist, the agent sees this block in its system prompt:

```xml
<learner_memory>
[Learner Profile]
  Name: Alice
  Programming Experience: beginner
  Strengths: pattern recognition, curiosity

[Observations]
  - Prefers step-by-step explanations
  - Has Python background but new to SQL

[Project: maji-ndogo-part1-v3]
  - Struggled with WHERE + AND combinations
  - Understood LIKE quickly after wildcard analogy
</learner_memory>
```

If no memories exist, the block is omitted entirely (no empty tags in the prompt).

---

## Agent Instructions

The agent receives `MEMORY_INSTRUCTIONS` telling it:

- **When to store**: learner shares name, agent spots learning patterns, relevant personal context
- **When NOT to**: don't store every interaction (chat history does that), don't echo "I remember you said..."
- **Scope guidance**: `global` = about the person, `project` = about their work on this specific project
- **Rate limit**: max 2-3 memories per session

---

## Debug Endpoint

```
GET /api/v1/debug/memory/{learner_id}?project_slug=maji-ndogo-part1-v3
```

Returns:
```json
{
  "learner_id": "learner-abc123",
  "project_slug": "maji-ndogo-part1-v3",
  "profile": { "name": "Alice", "strengths": ["pattern recognition"] },
  "global_memories": [{ "text": "Prefers step-by-step", "source": "agent" }],
  "project_memories": [{ "text": "Struggled with JOINs", "source": "agent" }],
  "prompt_block": "<learner_memory>..."
}
```

Gated behind `DEBUG=true`. Requires the memory store to be initialized.

---

## Tests

47 tests across 5 files:

| File | Tests | Covers |
|------|-------|--------|
| `test_schemas.py` | 5 | LearnerProfile defaults, MemoryEntry validation |
| `test_namespaces.py` | 6 | Namespace structure, learner/project isolation |
| `test_store.py` | 14 | CRUD, patch semantics, list dedup, scope isolation |
| `test_reader.py` | 8 | Prompt formatting, empty cases, partial data |
| `test_tools_memory.py` | 14 | Tool closures, store/fetch round-trips, metadata |

All tests use `InMemoryStore` — no database required.

```bash
uv run pytest services/agent-tutor/tests/test_memory/ -v
```
