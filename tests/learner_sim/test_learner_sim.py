"""
Tests for the Learner Simulator.

These tests verify:
1. Prompt generation
2. Simulator creation
3. State management
"""

import pytest

from agent.config import Config, LearnerSimulatorConfig, ModelConfig
from learner_sim.prompts import LEARNER_GREETING, build_learner_prompt
from learner_sim.simulator import LearnerSimulator, LearnerState, create_learner_graph


class TestLearnerPrompts:
    """Test learner prompt generation."""

    def test_build_learner_prompt_default(self):
        """Test building prompt with default values."""
        prompt = build_learner_prompt()

        assert "Thabo" in prompt
        assert "South Africa" in prompt
        assert "SQL" in prompt
        assert "60%" in prompt  # Default comprehension

    def test_build_learner_prompt_custom_rates(self):
        """Test building prompt with custom rates."""
        prompt = build_learner_prompt(
            comprehension_rate=80,
            confusion_rate=20,
            mistake_rate=30,
            question_rate=40,
        )

        assert "80%" in prompt
        assert "20%" in prompt
        assert "30%" in prompt
        assert "40%" in prompt

    def test_learner_greeting_exists(self):
        """Test that learner greeting is defined."""
        assert LEARNER_GREETING
        assert "Thabo" in LEARNER_GREETING
        assert "SQL" in LEARNER_GREETING

    def test_prompt_includes_persona_details(self):
        """Test that prompt includes key persona details."""
        prompt = build_learner_prompt()

        # Background
        assert "Johannesburg" in prompt
        assert "24" in prompt

        # Language patterns
        assert "Zulu" in prompt or "Sotho" in prompt
        assert "Eish" in prompt

        # Knowledge level
        assert "SELECT" in prompt
        assert "WHERE" in prompt


class TestLearnerState:
    """Test learner state management."""

    def test_learner_state_creation(self):
        """Test creating learner state."""
        state = LearnerState()

        assert state.messages == []
        assert state.turn_count == 0
        assert state.tasks_attempted == 0
        assert state.current_understanding == "neutral"

    def test_learner_state_with_values(self):
        """Test learner state with custom values."""
        state = LearnerState(
            turn_count=5,
            tasks_attempted=3,
            tasks_completed=2,
            current_understanding="understanding",
        )

        assert state.turn_count == 5
        assert state.tasks_attempted == 3
        assert state.tasks_completed == 2
        assert state.current_understanding == "understanding"


class TestLearnerGraph:
    """Test learner graph creation."""

    def test_create_learner_graph(self):
        """Test that learner graph can be created."""
        workflow = create_learner_graph()

        assert workflow is not None
        assert "learner" in workflow.nodes

    def test_learner_graph_compiles(self):
        """Test that learner graph compiles."""
        from langgraph.checkpoint.memory import MemorySaver

        workflow = create_learner_graph()
        graph = workflow.compile(checkpointer=MemorySaver())

        assert graph is not None


class TestLearnerSimulatorCreation:
    """Test learner simulator creation."""

    def test_create_learner_simulator_default(self):
        """Test creating simulator with default config."""
        simulator = create_learner_simulator()

        assert simulator is not None
        assert simulator.model is not None
        assert simulator.system_prompt is not None

    def test_create_learner_simulator_custom_config(self):
        """Test creating simulator with custom config."""
        config = Config(
            model=ModelConfig(
                learner_model="claude-haiku-4-5-20250514",
                learner_temperature=0.8,
            ),
            learner_sim=LearnerSimulatorConfig(
                comprehension_rate=0.7,
                mistake_rate=0.3,
            ),
        )

        simulator = create_learner_simulator(config=config)

        assert simulator is not None
        # Check that config values are reflected in prompt
        assert "70%" in simulator.system_prompt


# Import the function
from learner_sim.simulator import create_learner_simulator
