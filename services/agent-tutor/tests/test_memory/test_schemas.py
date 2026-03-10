"""Tests for learner memory schemas."""

from agent.memory.schemas import LearnerProfile, MemoryEntry


def test_learner_profile_defaults():
    """Empty profile has all None/empty defaults."""
    profile = LearnerProfile()
    assert profile.name is None
    assert profile.programming_experience is None
    assert profile.learning_style is None
    assert profile.communication_preferences is None
    assert profile.strengths == []
    assert profile.areas_for_growth == []
    assert profile.interests == []
    assert profile.background is None


def test_learner_profile_with_data():
    profile = LearnerProfile(
        name="Alice",
        programming_experience="beginner",
        strengths=["curiosity", "persistence"],
    )
    assert profile.name == "Alice"
    assert profile.strengths == ["curiosity", "persistence"]
    assert profile.learning_style is None  # unset fields stay None


def test_learner_profile_dump_excludes_none():
    profile = LearnerProfile(name="Bob")
    dumped = profile.model_dump(exclude_none=True)
    assert "name" in dumped
    assert "learning_style" not in dumped
    # List fields with default empty list are kept (not None)
    assert "strengths" in dumped


def test_memory_entry_defaults():
    entry = MemoryEntry(text="Likes visual examples")
    assert entry.text == "Likes visual examples"
    assert entry.context is None
    assert entry.source == "agent"


def test_memory_entry_full():
    entry = MemoryEntry(text="Struggled with JOINs", context="epic 3", source="system")
    assert entry.context == "epic 3"
    assert entry.source == "system"
