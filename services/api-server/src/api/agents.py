"""
Stateless agent management for the API.

Agents are created per-request (cheap — just object construction, no LLM calls).
Conversation state is persisted in a separate PostgreSQL database via
LangGraph's ``AsyncPostgresSaver``.  When no checkpoint DB is configured
**and** the environment is ``local``, falls back to in-memory ``MemorySaver``.
In ``dev``/``prod`` the checkpoint DB is required — startup fails hard if it
cannot connect.

Thread IDs are recorded in the ``conversation_threads`` table in the main
database so we can correlate learners, projects, and their chat history.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.config import get_config
from agent.graph import AgentWrapper, create_agent
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.settings import get_settings

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)

# ── Module-level state (initialised during FastAPI lifespan) ─────────
_checkpointer: BaseCheckpointSaver | None = None
_checkpoint_pool = None  # psycopg AsyncConnectionPool


async def init_checkpointer() -> None:
    """
    Initialise the shared LangGraph checkpointer.

    Called during FastAPI lifespan startup.

    - If ``LTT_CHECKPOINT_DATABASE_URL`` is set, connects to PostgreSQL.
      Failure raises in dev/prod (hard crash) and logs a warning in local.
    - If the URL is empty **and** env is ``local``, uses ``MemorySaver``.
    - If the URL is empty in ``dev``/``prod``, raises immediately.
    """
    global _checkpointer, _checkpoint_pool

    settings = get_settings()

    if settings.checkpoint_database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        try:
            _checkpoint_pool = AsyncConnectionPool(
                conninfo=settings.checkpoint_database_url,
                min_size=2,
                max_size=10,
                open=False,
            )
            await _checkpoint_pool.open()

            _checkpointer = AsyncPostgresSaver(_checkpoint_pool)
            await _checkpointer.setup()  # creates checkpoint tables if needed

            logger.info(
                "Agent checkpointer initialised (PostgresSaver → %s)",
                settings.checkpoint_database_url.rsplit("/", 1)[-1],
            )
        except Exception:
            if settings.env != "local":
                # dev/prod: fail hard — no silent fallback
                raise
            # local: warn and degrade
            logger.exception(
                "Failed to initialise PostgresSaver — falling back to MemorySaver (local only)"
            )
            _checkpointer = MemorySaver()
            _checkpoint_pool = None

    elif settings.env == "local":
        _checkpointer = MemorySaver()
        logger.info(
            "LTT_CHECKPOINT_DATABASE_URL not set — using in-memory MemorySaver (local only)"
        )
    else:
        raise RuntimeError(
            f"LTT_CHECKPOINT_DATABASE_URL is required in {settings.env} environment. "
            "Set it to a psycopg-format PostgreSQL URL "
            "(e.g. postgresql://user:pass@host:5432/ltt_checkpoints)."
        )


async def close_checkpointer() -> None:
    """Close the checkpoint connection pool (called during shutdown)."""
    global _checkpointer, _checkpoint_pool

    if _checkpoint_pool is not None:
        await _checkpoint_pool.close()
        _checkpoint_pool = None

    _checkpointer = None


def get_checkpointer() -> BaseCheckpointSaver:
    """Return the active checkpointer.

    Raises if called before ``init_checkpointer()`` (shouldn't happen
    in normal FastAPI flow since lifespan runs first).
    """
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialised. Call init_checkpointer() first.")
    return _checkpointer


def get_or_create_agent(
    learner_id: str,
    project_id: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> AgentWrapper:
    """
    Create a fresh agent for a single request.

    Agent construction is cheap (binds model + tools + prompt).
    Conversation state is persisted by the shared checkpointer so it
    survives across requests and even across multiple API server instances.
    """
    return create_agent(
        learner_id=learner_id,
        project_id=project_id,
        session_factory=session_factory,
        config=get_config(),
        checkpointer=get_checkpointer(),
    )
