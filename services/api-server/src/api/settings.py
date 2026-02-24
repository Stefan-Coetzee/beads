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
    database_url: str = (
        "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"
    )

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

    # ── Prod safety checks ───────────────────────────────────────────
    @model_validator(mode="after")
    def _validate_prod(self) -> "Settings":
        if self.env == "prod":
            errors: list[str] = []
            if not self.auth_enabled:
                errors.append("LTT_AUTH_ENABLED must be true in prod")
            if self.cors_origins == ["*"]:
                errors.append(
                    "LTT_CORS_ORIGINS must not be ['*'] in prod"
                )
            if not self.redis_url:
                errors.append("LTT_REDIS_URL is required in prod")
            if errors:
                raise ValueError(
                    "Production configuration errors:\n  - "
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
