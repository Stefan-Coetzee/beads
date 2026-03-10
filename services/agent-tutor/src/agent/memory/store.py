"""LearnerMemory — high-level wrapper around the LangGraph store."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from agent.memory.namespaces import (
    PROFILE_KEY,
    global_memories_ns,
    profile_ns,
    project_memories_ns,
)
from agent.memory.schemas import LearnerProfile, MemoryEntry

if TYPE_CHECKING:
    from langgraph.store.base import BaseStore

# Fields on LearnerProfile that are lists (append+dedupe on update)
_LIST_FIELDS = {"strengths", "areas_for_growth", "interests"}


class LearnerMemory:
    """Scoped memory operations for a single learner.

    Args:
        store: LangGraph BaseStore instance.
        learner_id: The learner this memory belongs to.
        project_slug: Optional stable project slug for project-scoped memories.
    """

    def __init__(
        self,
        store: BaseStore,
        learner_id: str,
        project_slug: str | None = None,
    ) -> None:
        self._store = store
        self._learner_id = learner_id
        self._project_slug = project_slug

    # ── Profile ──────────────────────────────────────────────────────

    async def get_profile(self) -> LearnerProfile:
        """Fetch the learner's profile, or return an empty one."""
        ns = profile_ns(self._learner_id)
        item = await self._store.aget(ns, PROFILE_KEY)
        if item is None:
            return LearnerProfile()
        return LearnerProfile(**item.value)

    async def update_profile(self, **kwargs) -> LearnerProfile:
        """Patch the learner profile.

        Only non-None kwargs are applied.  List fields (strengths,
        areas_for_growth, interests) use append-and-deduplicate
        semantics rather than replacement.
        """
        current = await self.get_profile()
        current_data = current.model_dump()

        for key, value in kwargs.items():
            if value is None:
                continue
            if key in _LIST_FIELDS and isinstance(value, list):
                # Append + deduplicate, preserving order
                existing = current_data.get(key, [])
                merged = list(dict.fromkeys(existing + value))
                current_data[key] = merged
            else:
                current_data[key] = value

        updated = LearnerProfile(**current_data)
        ns = profile_ns(self._learner_id)
        await self._store.aput(ns, PROFILE_KEY, updated.model_dump(exclude_none=True))
        return updated

    # ── Global memories ──────────────────────────────────────────────

    async def add_memory(
        self,
        text: str,
        context: str | None = None,
        source: str = "agent",
    ) -> str:
        """Store a global (cross-project) observation.  Returns the key."""
        key = str(uuid.uuid4())
        ns = global_memories_ns(self._learner_id)
        entry = MemoryEntry(text=text, context=context, source=source)
        await self._store.aput(ns, key, entry.model_dump())
        return key

    async def get_global_memories(self, limit: int = 20) -> list[MemoryEntry]:
        """Fetch the most recent global memories."""
        ns = global_memories_ns(self._learner_id)
        items = await self._store.asearch(ns, limit=limit)
        return [MemoryEntry(**item.value) for item in items]

    # ── Project memories ─────────────────────────────────────────────

    async def add_project_memory(
        self,
        text: str,
        context: str | None = None,
        source: str = "agent",
    ) -> str:
        """Store a project-scoped observation.  Returns the key.

        Raises ValueError if no project_slug was provided at init.
        """
        if not self._project_slug:
            raise ValueError("Cannot store project memory without a project_slug")
        key = str(uuid.uuid4())
        ns = project_memories_ns(self._learner_id, self._project_slug)
        entry = MemoryEntry(text=text, context=context, source=source)
        await self._store.aput(ns, key, entry.model_dump())
        return key

    async def get_project_memories(self, limit: int = 20) -> list[MemoryEntry]:
        """Fetch the most recent project-scoped memories.

        Returns empty list if no project_slug was provided.
        """
        if not self._project_slug:
            return []
        ns = project_memories_ns(self._learner_id, self._project_slug)
        items = await self._store.asearch(ns, limit=limit)
        return [MemoryEntry(**item.value) for item in items]
