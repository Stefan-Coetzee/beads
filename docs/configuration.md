# LTT Configuration Reference

All configuration is read from `LTT_*` environment variables.
**Single source of truth: `services/ltt-settings/src/ltt_settings/settings.py`**

Every service imports via:
```python
from ltt_settings import get_settings
s = get_settings()
```

Frontend config is in `apps/web/src/lib/config.ts` — no `process.env` anywhere else.

---

## Backend variables (`LTT_*`)

| Variable | Required | Default (local) | Description |
|---|---|---|---|
| `LTT_ENV` | no | `local` | Environment: `local`, `dev`, `staging`, `prod` |
| `LTT_DATABASE_URL` | **yes (deployed)** | `postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev` | Primary PostgreSQL connection string |
| `LTT_CHECKPOINT_DATABASE_URL` | **yes (prod)** | `""` | LangGraph checkpoint DB (psycopg sync). Empty → MemorySaver |
| `LTT_REDIS_URL` | **yes (deployed)** | `""` | Redis for LTI session storage. Empty → LTI disabled |
| `LTT_ANTHROPIC_API_KEY` | **yes (deployed)** | `""` | Anthropic API key for agent and summarisation |
| `LTT_AUTH_ENABLED` | **yes (prod)** | `false` | Require LTI auth on all workspace endpoints |
| `LTT_FRONTEND_URL` | **yes (deployed)** | `http://localhost:3000` | Where `/lti/launch` redirects after auth |
| `LTT_CORS_ORIGINS` | **yes (prod)** | `["*"]` | Allowed CORS origins (JSON list) |
| `LTT_CSP_FRAME_ANCESTORS` | no | `*` | `frame-ancestors` value in CSP header |
| `LTT_LTI_PLATFORM_URL` | no | `https://imbizo.alx-ai-tools.com` | Open edX issuer URL |
| `LTT_LTI_PLATFORM_CONFIG` | no | `configs/lti/platform.json` | Path or JSON string of platform registration |
| `LTT_LTI_PRIVATE_KEY` | **yes (prod)** | `configs/lti/private.key` | RSA private key — PEM string in prod, file path locally |
| `LTT_LTI_PUBLIC_KEY` | no | `configs/lti/public.key` | RSA public key — PEM string in prod, file path locally |
| `LTT_DEBUG` | no | `false` | Enable debug endpoints and verbose logging |
| `LTT_LOG_LEVEL` | no | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LTT_DEV_LEARNER_ID` | no | `learner-dev-001` | Default learner ID when auth is disabled |
| `LTT_DEV_PROJECT_ID` | no | `""` | Default project ID when auth is disabled |
| `LTT_TUTOR_MODEL` | no | `claude-haiku-4-5-20251001` | Anthropic model for the tutor agent |
| `LTT_MAX_CONVERSATION_TURNS` | no | `50` | Max turns before forcing a summary |
| `LTT_READY_TASKS_LIMIT` | no | `5` | Tasks surfaced to agent per call |
| `LTT_MAX_TOKENS` | no | `2048` | Max tokens per LLM response |
| `LTT_THINKING_ENABLED` | no | `false` | Enable extended thinking (Claude 3.7+) |
| `LTT_THINKING_BUDGET_TOKENS` | no | `2000` | Token budget when thinking is enabled |

### Startup validation

`Settings._validate_config` runs at startup and fails with a list of all
errors at once (not one at a time). Rules:

- **Any deployed env** (`dev`, `staging`, `prod`): `LTT_DATABASE_URL` must not
  point to localhost, `LTT_REDIS_URL` and `LTT_ANTHROPIC_API_KEY` must be set,
  `LTT_FRONTEND_URL` must not point to localhost.
- **Prod only**: `LTT_AUTH_ENABLED` must be `true`, `LTT_CORS_ORIGINS` must
  not be `["*"]`, `LTT_CHECKPOINT_DATABASE_URL` must be set, LTI keys must be
  PEM strings (not file paths).

---

## ECS / Secrets Manager

Values are injected at runtime — same variable names in every environment,
different values per environment via Secrets Manager.

| Secret path | ECS env var |
|---|---|
| `ltt/{env}/database_url` | `LTT_DATABASE_URL` |
| `ltt/{env}/checkpoint_db_url` | `LTT_CHECKPOINT_DATABASE_URL` |
| `ltt/{env}/redis_url` | `LTT_REDIS_URL` |
| `ltt/{env}/anthropic_api_key` | `LTT_ANTHROPIC_API_KEY` |
| `ltt/{env}/lti_private_key` | `LTT_LTI_PRIVATE_KEY` |
| `ltt/{env}/lti_public_key` | `LTT_LTI_PUBLIC_KEY` |
| `ltt/{env}/lti_platform_config` | `LTT_LTI_PLATFORM_CONFIG` |

Non-secret vars (`LTT_ENV`, `LTT_AUTH_ENABLED`, `LTT_FRONTEND_URL`, etc.) are
set directly in the ECS task definition `environment` block (see Terraform in
`infrastructure/terraform/modules/ltt-ecs/main.tf`).

---

## Frontend variables (`NEXT_PUBLIC_*`)

Defined in `apps/web/src/lib/config.ts`. No component reads `process.env` directly.

| Variable | Where set | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Build arg | API base URL. Leave empty in all deployed envs — browser uses relative URLs proxied by ALB |
| `NEXT_PUBLIC_DEBUG` | Build arg / ECS | Enables the debug login button in the UI |

Server-only (not sent to browser):

| Variable | Where set | Description |
|---|---|---|
| `LTT_API_URL` | ECS task def | Internal URL for Next.js → API server rewrites (local dev only) |
| `LTI_PLATFORM_URL` | ECS task def | Passed to `next.config.ts` for `frame-ancestors` CSP header |

---

## Local development

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
# Set LTT_ANTHROPIC_API_KEY=sk-ant-...
# Set LTT_REDIS_URL=redis://localhost:6379/0  (if testing LTI)
```

Run `docker compose up -d` to start PostgreSQL and Redis.
