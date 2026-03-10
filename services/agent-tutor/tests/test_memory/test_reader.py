"""Tests for memory prompt formatting."""

from agent.memory.reader import format_memories_for_prompt
from agent.memory.schemas import LearnerProfile, MemoryEntry


def test_empty_memories_returns_empty_string():
    result = format_memories_for_prompt(LearnerProfile(), [], [])
    assert result == ""


def test_profile_only():
    profile = LearnerProfile(name="Alice", programming_experience="beginner")
    result = format_memories_for_prompt(profile, [], [])
    assert "<learner_memory>" in result
    assert "Name: Alice" in result
    assert "Programming Experience: beginner" in result
    assert "[Observations]" not in result


def test_profile_list_fields():
    profile = LearnerProfile(strengths=["SQL", "curiosity"])
    result = format_memories_for_prompt(profile, [], [])
    assert "Strengths: SQL, curiosity" in result


def test_global_memories_only():
    memories = [
        MemoryEntry(text="Prefers visual examples"),
        MemoryEntry(text="Has Python background"),
    ]
    result = format_memories_for_prompt(LearnerProfile(), memories, [])
    assert "[Observations]" in result
    assert "- Prefers visual examples" in result
    assert "- Has Python background" in result


def test_project_memories():
    project_mems = [MemoryEntry(text="Struggled with WHERE + AND")]
    result = format_memories_for_prompt(
        LearnerProfile(), [], project_mems, project_slug="maji-ndogo"
    )
    assert "[Project: maji-ndogo]" in result
    assert "- Struggled with WHERE + AND" in result


def test_project_memories_without_slug_are_excluded():
    """Project memories need a slug to be rendered."""
    project_mems = [MemoryEntry(text="Some fact")]
    result = format_memories_for_prompt(LearnerProfile(), [], project_mems, project_slug=None)
    assert "[Project:" not in result


def test_full_output():
    profile = LearnerProfile(name="Bob", learning_style="hands-on")
    global_mems = [MemoryEntry(text="Quick learner")]
    project_mems = [MemoryEntry(text="Finished epic 1 fast")]
    result = format_memories_for_prompt(
        profile, global_mems, project_mems, project_slug="proj-slug"
    )
    assert "<learner_memory>" in result
    assert "</learner_memory>" in result
    assert "[Learner Profile]" in result
    assert "[Observations]" in result
    assert "[Project: proj-slug]" in result


def test_empty_list_fields_excluded():
    """Empty lists and None fields don't appear in output."""
    profile = LearnerProfile(name="Carol")
    result = format_memories_for_prompt(profile, [], [])
    assert "Strengths" not in result
    assert "Areas For Growth" not in result
