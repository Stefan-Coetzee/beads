---
description: 'Break an overview/README implementation plan into numbered phase docs with a central index. Use when creating phased implementation docs from a high-level plan, breaking down a README into per-phase detail docs (01-*.md, 02-*.md), or structuring multi-phase work into the LTT docs/ conventions. Triggers: "plan phases", "break into phases", "create phase docs", "implementation plan docs".'
allowed-tools: Read, Grep, Glob, Edit, Write, Agent
---

# Plan Phases

Break a high-level implementation plan (typically a `README.md` in a `docs/` subfolder) into individual numbered phase documents plus a central overview that links them.

## Workflow

### 1. Gather Context

Read the source overview doc (passed as `$0` argument or identified from conversation context).

Identify:
- How many phases are described
- What each phase changes (models, services, migrations, tests, API routes, frontend)
- Dependencies between phases (which phases unblock others)
- Key decisions and their rationale

### 2. Explore the Codebase

For each phase, use Explore agents in parallel to verify:
- The files mentioned actually exist and find exact line numbers
- Current state of models/fields/functions referenced
- Test files that need updating
- Any gaps between what the plan says and what the code actually has

### 3. Create Phase Documents

Create one doc per phase following the naming convention `NN-short-name.md` (e.g., `01-fix-ingest-drops.md`).

Read `references/phase-template.md` for the canonical structure. Key sections:

- **Header**: Phase number, title, one-line goal, status badge
- **Current State**: What exists today (with file paths and line numbers)
- **Changes**: Detailed implementation steps grouped by layer (model, migration, service, test)
- **File Map**: Every file that needs changes, what changes, and why
- **Test Plan**: Specific tests to add or update
- **Verification**: Commands to confirm the phase works
- **Depends On / Unblocks**: Phase dependency graph

### 4. Create or Update the Overview

The folder's `README.md` should become (or remain) the central index. Structure:

```markdown
# Feature Name — Implementation Plan

> One-line summary.

**Status**: [status]

---

## The Gap
[What's wrong / what's missing — from the original overview]

## Phase Summary
| Phase | Title | Status | Depends On |
|-------|-------|--------|------------|
| 01 | Short name | Not started | — |
| 02 | Short name | Not started | 01 |

## Documents
| Doc | Description |
|---|---|
| [01-short-name.md](01-short-name.md) | One-line description |
| [02-short-name.md](02-short-name.md) | One-line description |

## Key Decisions
[Moved from the original overview — rationale for major choices]

## Reference Files
[Table of source files, schemas, related docs]
```

### 5. Verify Completeness

Confirm:
- Every phase from the overview has a corresponding numbered doc
- Every file mentioned in any phase doc actually exists (or is explicitly marked as "new file")
- Phase dependencies form a DAG (no circular deps)
- The overview's phase summary table matches the actual docs
- No information from the original overview was lost

## Conventions (from existing LTT docs)

These patterns are established across `docs/lti/`, `docs/deployment/`, and `docs/production-hardening-plan.md`:

1. **Phase titles are functional** — describe what's being done, not when ("Fix ingest drops", not "Week 1")
2. **File maps tie phases to files** — developers see exactly where to edit
3. **Key decisions explain WHY** — not just what, but the reasoning
4. **Numbered docs use zero-padded prefix** — `01-`, `02-`, ..., `10-`
5. **README is the index** — paired with numbered docs in the same folder
6. **Verification sections are runnable** — actual commands, not prose
7. **Status tracking** — phases marked "Not started" / "In progress" / "Complete"
8. **Dependencies bracketed** — `[foundation]`, `[P0 security]`, `[unblocks grading]`
9. **Companion docs** (like `grading.md`, `rest-endpoint.md`) stay as-is — phase docs reference them, don't duplicate them

## Anti-Patterns

- Do NOT duplicate content from companion docs into phase docs — reference them
- Do NOT create phase docs for work that's already complete — mark as "Complete" in the summary
- Do NOT add phases beyond what the overview describes — stay faithful to the plan
- Do NOT guess file paths or line numbers — verify with Grep/Glob first
