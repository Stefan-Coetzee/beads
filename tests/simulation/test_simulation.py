"""
Tests for the Simulation Runner.

These tests verify:
1. Conversation logging
2. Configuration handling
3. Runner creation
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agent.config import Config, ModelConfig, SimulationConfig
from simulation.runner import ConversationLog, ConversationRunner, ConversationTurn


class TestConversationTurn:
    """Test conversation turn dataclass."""

    def test_turn_creation(self):
        """Test creating a conversation turn."""
        turn = ConversationTurn(
            speaker="tutor",
            message="Hello, how can I help you?",
        )

        assert turn.speaker == "tutor"
        assert turn.message == "Hello, how can I help you?"
        assert turn.timestamp is not None
        assert turn.metadata == {}

    def test_turn_with_metadata(self):
        """Test turn with metadata."""
        turn = ConversationTurn(
            speaker="learner",
            message="I need help with SQL",
            metadata={"turn": 1, "confidence": 0.8},
        )

        assert turn.metadata["turn"] == 1
        assert turn.metadata["confidence"] == 0.8


class TestConversationLog:
    """Test conversation logging."""

    def test_log_creation(self):
        """Test creating a conversation log."""
        log = ConversationLog(
            learner_id="learner-123",
            project_id="proj-abc",
        )

        assert log.learner_id == "learner-123"
        assert log.project_id == "proj-abc"
        assert log.turns == []
        assert log.started_at is not None

    def test_add_turn(self):
        """Test adding turns to log."""
        log = ConversationLog()

        log.add_turn("learner", "Hello!")
        log.add_turn("tutor", "Hi there!")

        assert len(log.turns) == 2
        assert log.turns[0].speaker == "learner"
        assert log.turns[1].speaker == "tutor"

    def test_add_turn_with_metadata(self):
        """Test adding turn with metadata."""
        log = ConversationLog()

        log.add_turn("tutor", "Let's start", turn=1, tool_calls=["get_ready"])

        assert log.turns[0].metadata["turn"] == 1
        assert log.turns[0].metadata["tool_calls"] == ["get_ready"]

    def test_save_log(self):
        """Test saving log to file."""
        log = ConversationLog(
            learner_id="learner-test",
            project_id="proj-test",
        )
        log.add_turn("learner", "Hello")
        log.add_turn("tutor", "Hi!")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_log.json"
            log.save(path)

            assert path.exists()

            with open(path) as f:
                data = json.load(f)

            assert data["learner_id"] == "learner-test"
            assert data["project_id"] == "proj-test"
            assert len(data["turns"]) == 2
            assert data["ended_at"] is not None


class TestConversationRunnerCreation:
    """Test conversation runner creation."""

    @pytest.mark.asyncio
    async def test_runner_creation(self, async_session):
        """Test creating a conversation runner."""
        runner = ConversationRunner(
            learner_id="learner-123",
            project_id="proj-abc",
            session=async_session,
        )

        assert runner.learner_id == "learner-123"
        assert runner.project_id == "proj-abc"
        assert runner.tutor is not None
        assert runner.learner is not None
        assert runner.log is not None

    @pytest.mark.asyncio
    async def test_runner_with_custom_config(self, async_session):
        """Test runner with custom configuration."""
        config = Config(
            model=ModelConfig(
                tutor_model="claude-haiku-4-5-20250514",
            ),
            simulation=SimulationConfig(
                max_turns=10,
                turn_delay=0.1,
            ),
        )

        runner = ConversationRunner(
            learner_id="learner-123",
            project_id="proj-abc",
            session=async_session,
            config=config,
        )

        assert runner.config.simulation.max_turns == 10
        assert runner.config.model.tutor_model == "claude-haiku-4-5-20250514"


class TestConfig:
    """Test configuration handling."""

    def test_default_config(self):
        """Test default configuration values."""
        from agent.config import get_config

        config = get_config()

        assert config.model.tutor_model == "claude-haiku-4-5-20250514"
        assert config.model.learner_model == "claude-haiku-4-5-20250514"
        assert config.learner_sim.comprehension_rate == 0.6
        assert config.simulation.max_turns == 30

    def test_custom_config(self):
        """Test custom configuration."""
        from agent.config import create_config

        config = create_config(
            model=ModelConfig(tutor_model="claude-sonnet-4-20250514"),
            simulation=SimulationConfig(max_turns=50),
        )

        assert config.model.tutor_model == "claude-sonnet-4-20250514"
        assert config.simulation.max_turns == 50
