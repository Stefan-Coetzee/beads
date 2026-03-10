"""Tests for LearnerMemory store operations using InMemoryStore."""

import pytest
from agent.memory.store import LearnerMemory
from langgraph.store.memory import InMemoryStore


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def memory(store):
    return LearnerMemory(store, "learner-1", "maji-ndogo")


@pytest.fixture
def memory_no_project(store):
    return LearnerMemory(store, "learner-1")


# ── Profile ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_empty_profile(memory):
    profile = await memory.get_profile()
    assert profile.name is None
    assert profile.strengths == []


@pytest.mark.asyncio
async def test_update_profile_basic(memory):
    updated = await memory.update_profile(name="Alice", programming_experience="beginner")
    assert updated.name == "Alice"
    assert updated.programming_experience == "beginner"


@pytest.mark.asyncio
async def test_update_profile_patch_semantics(memory):
    """Only provided fields change; others are preserved."""
    await memory.update_profile(name="Alice", learning_style="visual")
    updated = await memory.update_profile(programming_experience="intermediate")
    assert updated.name == "Alice"  # preserved
    assert updated.learning_style == "visual"  # preserved
    assert updated.programming_experience == "intermediate"  # new


@pytest.mark.asyncio
async def test_update_profile_list_append_dedupe(memory):
    """List fields append and deduplicate."""
    await memory.update_profile(strengths=["SQL", "curiosity"])
    updated = await memory.update_profile(strengths=["curiosity", "persistence"])
    # Should be ["SQL", "curiosity", "persistence"] — deduplicated, order preserved
    assert updated.strengths == ["SQL", "curiosity", "persistence"]


@pytest.mark.asyncio
async def test_update_profile_all_list_fields(memory):
    """All three list fields use append+dedupe."""
    await memory.update_profile(
        strengths=["a"],
        areas_for_growth=["b"],
        interests=["c"],
    )
    updated = await memory.update_profile(
        strengths=["a", "d"],
        areas_for_growth=["b", "e"],
        interests=["c", "f"],
    )
    assert updated.strengths == ["a", "d"]
    assert updated.areas_for_growth == ["b", "e"]
    assert updated.interests == ["c", "f"]


# ── Global memories ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_and_get_global_memory(memory):
    key = await memory.add_memory("Prefers step-by-step explanations")
    assert key  # UUID string

    memories = await memory.get_global_memories()
    assert len(memories) == 1
    assert memories[0].text == "Prefers step-by-step explanations"
    assert memories[0].source == "agent"


@pytest.mark.asyncio
async def test_global_memory_with_context(memory):
    await memory.add_memory("Struggled with WHERE", context="epic 2", source="system")
    memories = await memory.get_global_memories()
    assert memories[0].context == "epic 2"
    assert memories[0].source == "system"


@pytest.mark.asyncio
async def test_global_memory_limit(memory):
    for i in range(25):
        await memory.add_memory(f"Fact {i}")
    memories = await memory.get_global_memories(limit=10)
    assert len(memories) <= 10


# ── Project memories ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_and_get_project_memory(memory):
    key = await memory.add_project_memory("Completed epic 1 quickly")
    assert key

    memories = await memory.get_project_memories()
    assert len(memories) == 1
    assert memories[0].text == "Completed epic 1 quickly"


@pytest.mark.asyncio
async def test_project_memory_without_slug(memory_no_project):
    """Cannot store project memory without project_slug."""
    with pytest.raises(ValueError, match="project_slug"):
        await memory_no_project.add_project_memory("some fact")


@pytest.mark.asyncio
async def test_project_memory_get_without_slug(memory_no_project):
    """Returns empty list when no project_slug."""
    memories = await memory_no_project.get_project_memories()
    assert memories == []


# ── Isolation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_learner_isolation(store):
    """Different learners have separate memories."""
    mem_a = LearnerMemory(store, "learner-a", "proj")
    mem_b = LearnerMemory(store, "learner-b", "proj")

    await mem_a.add_memory("Fact for A")
    await mem_b.add_memory("Fact for B")

    a_mems = await mem_a.get_global_memories()
    b_mems = await mem_b.get_global_memories()

    assert len(a_mems) == 1
    assert a_mems[0].text == "Fact for A"
    assert len(b_mems) == 1
    assert b_mems[0].text == "Fact for B"


@pytest.mark.asyncio
async def test_project_isolation(store):
    """Same learner, different projects have separate project memories."""
    mem_a = LearnerMemory(store, "learner-1", "project-a")
    mem_b = LearnerMemory(store, "learner-1", "project-b")

    await mem_a.add_project_memory("Fact for project A")
    await mem_b.add_project_memory("Fact for project B")

    a_mems = await mem_a.get_project_memories()
    b_mems = await mem_b.get_project_memories()

    assert len(a_mems) == 1
    assert a_mems[0].text == "Fact for project A"
    assert len(b_mems) == 1
    assert b_mems[0].text == "Fact for project B"


@pytest.mark.asyncio
async def test_global_vs_project_isolation(memory):
    """Global and project memories are separate namespaces."""
    await memory.add_memory("Global fact")
    await memory.add_project_memory("Project fact")

    global_mems = await memory.get_global_memories()
    project_mems = await memory.get_project_memories()

    assert len(global_mems) == 1
    assert global_mems[0].text == "Global fact"
    assert len(project_mems) == 1
    assert project_mems[0].text == "Project fact"
