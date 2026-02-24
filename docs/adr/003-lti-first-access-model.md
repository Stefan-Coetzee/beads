# ADR-003: LTI-First Access Model

**Status**: Accepted
**Date**: 2026-02

---

## Context

LTT was originally built with a standalone access mode: cookie-based learner IDs, a home page with project selection, and API endpoints that accept raw `learner_id` parameters. This was useful for development but is not viable for production.

The system needs to run inside Open edX (imbizo.alx-ai-tools.com) where learners are authenticated by the LMS. LTI 1.3 provides standards-based authentication, identity mapping, and grade passback.

## Decision

**LTI 1.3 is the only entry point for learners.** There is no standalone mode in production.

### Access Flow

```
Open edX → POST /lti/login (OIDC) → POST /lti/launch (JWT validation)
  → map LTI user to LTT learner → 302 to /workspace/{project_id}
```

### Key Design Choices

1. **User identity** comes from the LTI JWT `sub` + `iss` claims, mapped to an LTT `learner_id` via the `lti_user_mappings` table
2. **Project assignment** comes from LTI custom params (`custom.project_id`), set by the instructor in Studio
3. **Session state** is tracked via `launch_id` (stored in Redis + DB), not cookies
4. **Grade passback** uses LTI Advantage AGS, triggered on task completion
5. **Frontend** runs in an iframe inside Open edX, using `sessionStorage` for LTI context

### What This Replaces

| Standalone Pattern | LTI Replacement |
|---|---|
| Cookie-based learner ID | LTI JWT `sub` claim → `lti_user_mappings` |
| Home page project selector | `custom.project_id` in LTI launch |
| Raw `learner_id` API params | `X-LTI-Launch-Id` header → resolved from Redis |
| No authentication | JWT validation + OIDC |
| No grade sync | AGS grade passback |

## Consequences

### Positive
- Proper authentication — no impersonation possible
- Grade sync with LMS gradebook
- User identity managed by the LMS (SSO)
- Works with any LTI 1.3 compatible LMS (not just Open edX)

### Negative
- Requires Redis for launch state
- Requires RSA key management
- Dev workflow requires a tunnel (cloudflared/ngrok) for LTI testing
- Platform configuration in Studio is manual

### Cleanup Required

Standalone-mode code must be removed or gated. See `docs/lti/cleanup/` for the full audit.
