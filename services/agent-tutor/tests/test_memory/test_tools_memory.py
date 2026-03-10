"""Tests for memory tool closures (store_memory, update_learner_profile).

These verify the tool functions created by _create_memory_tools() actually
write to and read from the store correctly.
"""

import json

import pytest
from agent.memory.store import LearnerMemory
from agent.tools import _create_memory_tools
from langgraph.store.memory import InMemoryStore


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def memory_tools(store):
    return _create_memory_tools(
        store=store,
        learner_id="learner-1",
        project_slug="maji-ndogo-part1-v3",
    )


@pytest.fixture
def memory_tools_no_slug(store):
    return _create_memory_tools(
        store=store,
        learner_id="learner-1",
        project_slug=None,
    )


def _tool_by_name(tools, name):
    return next(t for t in tools if t.name == name)


# ── store_memory tool ────────────────────────────────────────────────


class TestStoreMemoryTool:
    @pytest.mark.asyncio
    async def test_store_project_memory(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "store_memory")
        result = await tool.ainvoke({"text": "Struggles with JOINs", "scope": "project"})
        data = json.loads(result)

        assert data["stored"] is True
        assert data["scope"] == "project"
        assert data["key"]  # UUID

        # Verify it's actually in the store
        mem = LearnerMemory(store, "learner-1", "maji-ndogo-part1-v3")
        memories = await mem.get_project_memories()
        assert len(memories) == 1
        assert memories[0].text == "Struggles with JOINs"

    @pytest.mark.asyncio
    async def test_store_global_memory(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "store_memory")
        result = await tool.ainvoke({"text": "Prefers step-by-step", "scope": "global"})
        data = json.loads(result)

        assert data["stored"] is True
        assert data["scope"] == "global"

        mem = LearnerMemory(store, "learner-1")
        memories = await mem.get_global_memories()
        assert len(memories) == 1
        assert memories[0].text == "Prefers step-by-step"

    @pytest.mark.asyncio
    async def test_store_memory_with_context(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "store_memory")
        await tool.ainvoke({
            "text": "Understood LIKE after wildcard analogy",
            "context": "Working on task proj-123.2.3",
            "scope": "project",
        })

        mem = LearnerMemory(store, "learner-1", "maji-ndogo-part1-v3")
        memories = await mem.get_project_memories()
        assert memories[0].context == "Working on task proj-123.2.3"

    @pytest.mark.asyncio
    async def test_store_memory_no_slug_falls_back_to_global(self, memory_tools_no_slug, store):
        """When project_slug is None, even 'project' scope goes to global."""
        tool = _tool_by_name(memory_tools_no_slug, "store_memory")
        result = await tool.ainvoke({"text": "Some observation", "scope": "project"})
        data = json.loads(result)

        assert data["stored"] is True
        # Falls back to global because no slug
        mem = LearnerMemory(store, "learner-1")
        memories = await mem.get_global_memories()
        assert len(memories) == 1

    @pytest.mark.asyncio
    async def test_store_multiple_memories(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "store_memory")
        await tool.ainvoke({"text": "Fact 1", "scope": "global"})
        await tool.ainvoke({"text": "Fact 2", "scope": "global"})
        await tool.ainvoke({"text": "Fact 3", "scope": "project"})

        mem = LearnerMemory(store, "learner-1", "maji-ndogo-part1-v3")
        global_mems = await mem.get_global_memories()
        project_mems = await mem.get_project_memories()
        assert len(global_mems) == 2
        assert len(project_mems) == 1


# ── update_learner_profile tool ──────────────────────────────────────


class TestUpdateProfileTool:
    @pytest.mark.asyncio
    async def test_update_name(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "update_learner_profile")
        result = await tool.ainvoke({"name": "Alice"})
        data = json.loads(result)

        assert data["updated"] is True
        assert "name" in data["fields"]

        mem = LearnerMemory(store, "learner-1")
        profile = await mem.get_profile()
        assert profile.name == "Alice"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "update_learner_profile")
        await tool.ainvoke({
            "name": "Bob",
            "programming_experience": "beginner",
            "learning_style": "hands-on",
        })

        mem = LearnerMemory(store, "learner-1")
        profile = await mem.get_profile()
        assert profile.name == "Bob"
        assert profile.programming_experience == "beginner"
        assert profile.learning_style == "hands-on"

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_not_updated(self, memory_tools):
        tool = _tool_by_name(memory_tools, "update_learner_profile")
        result = await tool.ainvoke({})
        data = json.loads(result)

        assert data["updated"] is False
        assert "No fields" in data["reason"]

    @pytest.mark.asyncio
    async def test_update_list_fields_append(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "update_learner_profile")

        await tool.ainvoke({"strengths": ["pattern recognition"]})
        await tool.ainvoke({"strengths": ["curiosity"]})

        mem = LearnerMemory(store, "learner-1")
        profile = await mem.get_profile()
        assert profile.strengths == ["pattern recognition", "curiosity"]

    @pytest.mark.asyncio
    async def test_update_preserves_existing_fields(self, memory_tools, store):
        tool = _tool_by_name(memory_tools, "update_learner_profile")

        await tool.ainvoke({"name": "Alice", "background": "CS student"})
        await tool.ainvoke({"learning_style": "visual"})

        mem = LearnerMemory(store, "learner-1")
        profile = await mem.get_profile()
        assert profile.name == "Alice"
        assert profile.background == "CS student"
        assert profile.learning_style == "visual"


# ── Tool metadata ────────────────────────────────────────────────────


class TestMemoryToolMetadata:
    def test_tools_have_correct_names(self, memory_tools):
        names = {t.name for t in memory_tools}
        assert names == {"store_memory", "update_learner_profile"}

    def test_tools_have_descriptions(self, memory_tools):
        for tool in memory_tools:
            assert tool.description
            assert len(tool.description) > 20

    def test_tools_have_schemas(self, memory_tools):
        for tool in memory_tools:
            assert tool.args_schema is not None

    def test_tools_are_async(self, memory_tools):
        for tool in memory_tools:
            assert tool.coroutine is not None
            assert callable(tool.coroutine)
