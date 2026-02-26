"""
Single source of truth for all LTT_* environment variables.

Every service (ltt-core, api-server, agent-tutor) imports from here.
No service reads os.getenv directly — change a variable name here and
it propagates everywhere automatically.

All variables use the LTT_ prefix.  The same variable names are used in
every environment; the *values* differ (injected via Secrets Manager in
ECS, or set in .env for local dev).

Usage::

    from ltt_settings import get_settings
    s = get_settings()
    print(s.database_url, s.tutor_model)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All LTT application settings, loaded from LTT_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LTT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────────────────────
    env: Literal["local", "dev", "staging", "prod"] = "local"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"

    # Separate DB for LangGraph conversation checkpoints (psycopg sync driver).
    # Empty string → fall back to in-memory MemorySaver (no persistence).
    checkpoint_database_url: str = ""

    # ── Redis ─────────────────────────────────────────────────────────────────
    # Empty string → LTI disabled; agent uses MemorySaver.
    redis_url: str = ""

    # ── Auth ──────────────────────────────────────────────────────────────────
    auth_enabled: bool = False
    dev_learner_id: str = "learner-dev-001"
    dev_project_id: str = ""

    # ── LTI ───────────────────────────────────────────────────────────────────
    # Values starting with "-----BEGIN" are PEM strings; otherwise file paths.
    # Platform config starting with "{" or "[" is parsed as JSON directly.
    lti_platform_url: str = "https://imbizo.alx-ai-tools.com"
    lti_platform_config: str = "configs/lti/platform.json"
    lti_private_key: str = "configs/lti/private.key"
    lti_public_key: str = "configs/lti/public.key"

    # ── CORS / CSP ────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]
    csp_frame_ancestors: str = "*"

    # ── Frontend ──────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Observability ─────────────────────────────────────────────────────────
    debug: bool = False
    log_level: str = "INFO"

    # ── AI / Agent ────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # Tutor model — the LLM used to teach learners.
    tutor_model: str = "claude-haiku-4-5-20251001"

    # Max conversation turns before forcing a summary checkpoint.
    max_conversation_turns: int = 50

    # How many ready tasks to surface to the agent at once.
    ready_tasks_limit: int = 5

    # Max tokens per LLM response.
    max_tokens: int = 2048

    # Extended thinking (Claude 3.7+). Disabled by default.
    thinking_enabled: bool = False
    thinking_budget_tokens: int = 2000

    # ── Startup validation ────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_config(self) -> Settings:
        """
        Fail fast on misconfiguration.  All errors collected before raising so
        a single startup failure lists every problem at once.
        """
        errors: list[str] = []

        # ── Any deployed environment (dev / staging / prod — not local) ───────
        if self.env != "local":
            if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
                errors.append(
                    "LTT_DATABASE_URL must not point to localhost "
                    f"(env={self.env!r} — inject the RDS endpoint via Secrets Manager)"
                )

            if not self.redis_url:
                errors.append(
                    "LTT_REDIS_URL is required in deployed environments "
                    "(LTI sessions and grade passback will not function)"
                )

            if not self.anthropic_api_key:
                errors.append(f"LTT_ANTHROPIC_API_KEY is required in env={self.env!r}")

            if "localhost" in self.frontend_url or "127.0.0.1" in self.frontend_url:
                errors.append(
                    "LTT_FRONTEND_URL must not point to localhost "
                    f"(env={self.env!r} — LTI launch redirects will break)"
                )

        # ── Production only ───────────────────────────────────────────────────
        if self.env == "prod":
            if not self.auth_enabled:
                errors.append("LTT_AUTH_ENABLED must be true in prod")

            if self.cors_origins == ["*"]:
                errors.append("LTT_CORS_ORIGINS must not be ['*'] in prod")

            if not self.checkpoint_database_url:
                errors.append(
                    "LTT_CHECKPOINT_DATABASE_URL is required in prod "
                    "(chat history will not persist without it)"
                )

            if not self.lti_private_key.startswith("-----BEGIN"):
                errors.append(
                    "LTT_LTI_PRIVATE_KEY must be a PEM string in prod "
                    "(inject via Secrets Manager — local file paths don't exist in containers)"
                )

            if not self.lti_public_key.startswith("-----BEGIN"):
                errors.append(
                    "LTT_LTI_PUBLIC_KEY must be a PEM string in prod (inject via Secrets Manager)"
                )

        if errors:
            raise ValueError(
                f"[LTT env={self.env!r}] Configuration errors — fix before deploying:\n  - "
                + "\n  - ".join(errors)
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache (used in tests)."""
    get_settings.cache_clear()
