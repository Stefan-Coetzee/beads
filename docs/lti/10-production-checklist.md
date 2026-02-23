# Production Checklist

> What must be done before LTT runs in production behind LTI.

---

## Security

- [ ] **Tighten CORS** — Replace `allow_origins=["*"]` in `app.py` with the specific frontend and platform URLs
- [ ] **Tighten CSP** — Replace `frame-ancestors *` with `frame-ancestors https://imbizo.alx-ai-tools.com 'self'` in both `app.py` and `next.config.ts`
- [ ] **Remove debug endpoints** — Delete or permanently disable `/lti/debug/*` routes (see cleanup.md)
- [ ] **Remove debug UI** — Remove `DebugButton` component and `/debug` page from production builds
- [ ] **Validate LTI context on API endpoints** — Add middleware to require `X-LTI-Launch-Id` header on all `/api/v1/*` endpoints (see cleanup.md)
- [ ] **Remove `ensure_learner_exists()` auto-creation** — Learners should only be created via LTI launch
- [ ] **Remove fallback learner IDs** — Delete `"learner-dev-001"` fallbacks from frontend
- [ ] **Rotate RSA keys** — Generate production keys, store in secrets manager, not filesystem
- [ ] **Set `SameSite=None; Secure`** on all cookies (adapter already does this)
- [ ] **HTTPS only** — Ensure `LTT_FRONTEND_URL` uses https in production

## Infrastructure

- [ ] **Redis persistence** — Configure Redis with AOF or RDB persistence for launch data
- [ ] **Redis password** — Set `requirepass` in Redis config
- [ ] **PostgreSQL credentials** — Use production credentials, not dev defaults
- [ ] **Tunnel → static domain** — Replace cloudflared quick tunnel with named tunnel or direct domain
- [ ] **Health checks** — `/health` endpoint should not expose internal state (`lti_enabled` field)

## Monitoring

- [ ] **Structured logging** — Replace print statements with proper logging
- [ ] **Error tracking** — Add Sentry or equivalent
- [ ] **Grade passback monitoring** — Alert on AGS failures
- [ ] **Redis connection monitoring** — Alert on Redis down (breaks all LTI sessions)

## Testing

- [ ] **End-to-end LTI flow** — Full launch from Open edX through to grade passback
- [ ] **JWT expiry handling** — Verify behavior when launch data expires in Redis
- [ ] **Multi-deployment** — Test with multiple `deployment_id` values
- [ ] **NRPS fallback** — Verify name/email resolution when standard claims are missing
