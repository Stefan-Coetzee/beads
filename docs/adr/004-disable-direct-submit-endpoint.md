# ADR-004: Disable Direct Submit Endpoint

**Status**: Accepted
**Date**: 2026-02-23

---

## Context

The codebase has two paths for submitting learner work:

1. **Agent chat flow** (`POST /api/v1/chat`) — the learner chats with the Socratic tutor agent, which decides when to call the `submit` tool internally. The agent provides pedagogical feedback, hints, and follow-up questions.

2. **Direct submit endpoint** (`POST /api/v1/task/{taskId}/submit`) — a REST endpoint that creates a submission and runs validation directly. No LLM involved, immediate pass/fail.

The direct endpoint was built speculatively for a "Run" button workflow, but:

- It is **not called by any frontend component** (dead code on the frontend)
- The only validator is `SimpleValidator` (non-empty check) — no meaningful feedback
- It bypasses the agent's pedagogical flow, which is the core value proposition
- Without real validation rules (SQL result checks, code tests), the endpoint gives learners a false sense of progress

## Decision

**Disable the direct submit endpoint.** Comment out the route handler and frontend API method. All submissions go through the agent chat flow.

The code is preserved (commented, not deleted) for when custom validators are implemented. At that point, a direct "Run & Check" button makes sense — immediate SQL result validation without waiting for an LLM response.

### Re-enable criteria

The endpoint should be re-enabled when:

1. Custom validators exist (SQL result comparison, code test runners, etc.)
2. The validator provides meaningful feedback beyond pass/fail
3. There is a clear UX for "quick check" vs "ask the tutor"

## Consequences

### Positive
- Single submission path simplifies the mental model
- All submissions get pedagogical context from the agent
- No half-built feature creating confusion

### Negative
- Every submission requires an LLM call (latency + cost)
- "Run" button in the workspace only executes locally — doesn't record a submission

### Mitigations
- Local execution (SQL.js, Python sandbox) still works instantly for the "Run" button
- The agent can be prompted to do quick validation without lengthy feedback
- When validators are ready, re-enabling is a simple uncomment
