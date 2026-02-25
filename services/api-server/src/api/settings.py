"""
Central configuration for the API server.

All settings are read from environment variables with the ``LTT_`` prefix
(e.g. ``LTT_ENV=prod``, ``LTT_DATABASE_URL=...``).  Pydantic validates and
casts values on startup.

Usage::

    from api.settings import get_settings
    settings = get_settings()
    print(settings.env, settings.database_url)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from ``LTT_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LTT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────────────
    env: Literal["local", "dev", "prod"] = "local"

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"

    # ── Checkpoint DB ────────────────────────────────────────────────
    # Separate database for LangGraph conversation checkpoints (psycopg).
    # Uses plain ``postgresql://`` scheme (not +asyncpg).
    # Empty string = fall back to in-memory MemorySaver (no persistence).
    checkpoint_database_url: str = ""

    # ── Redis ────────────────────────────────────────────────────────
    # Empty string = LTI disabled, agent uses MemorySaver.
    redis_url: str = ""

    # ── Auth ─────────────────────────────────────────────────────────
    auth_enabled: bool = False  # True in prod; False keeps local/dev working
    dev_learner_id: str = "learner-dev-001"
    dev_project_id: str = ""

    # ── LTI ──────────────────────────────────────────────────────────
    # Values starting with "-----BEGIN" are treated as PEM strings;
    # otherwise they are read as file paths.  Same for platform config:
    # if it starts with "{" or "[", it's parsed as JSON directly.
    lti_platform_url: str = "https://imbizo.alx-ai-tools.com"
    lti_platform_config: str = "configs/lti/platform.json"
    lti_private_key: str = "configs/lti/private.key"
    lti_public_key: str = "configs/lti/public.key"

    # ── CORS ─────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    # ── CSP ──────────────────────────────────────────────────────────
    csp_frame_ancestors: str = "*"

    # ── Frontend ─────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Security / Debug ─────────────────────────────────────────────
    debug: bool = False
    log_level: str = "INFO"

    # ── Agent ────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── Startup validation ───────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_config(self) -> Settings:
        """
        Fail fast if required settings are missing or misconfigured.

        All errors are collected before raising so a single startup failure
        reveals every missing variable at once rather than one at a time.
        """
        errors: list[str] = []

        # ── Any deployed environment (dev or prod — not local) ────────
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

        # ── Production only ───────────────────────────────────────────
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

            # LTI keys must be PEM strings injected by Secrets Manager,
            # not local file paths (those don't exist inside the container).
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
    """Clear the settings cache (for testing)."""
    get_settings.cache_clear()
