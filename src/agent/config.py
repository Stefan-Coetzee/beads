"""
Centralized configuration for the Socratic Learning Agent.

All configurable settings should be defined here for easy management.
"""

import os
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for LLM models."""

    # Tutor agent model - uses a capable model for teaching
    tutor_model: str = "claude-haiku-4-5-20251001"

    # Learner simulator model - can use same or different model
    learner_model: str = "claude-haiku-4-5-20251001"

    # Temperature settings
    tutor_temperature: float = 0.7  # Some creativity for teaching
    learner_temperature: float = 0.9  # More variability for realistic learner behavior

    # Max tokens for responses
    max_tokens: int = 2048


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    # Maximum conversation turns before forcing a summary
    max_conversation_turns: int = 50

    # How many ready tasks to fetch at once
    ready_tasks_limit: int = 5

    # Default checkpointer type: "memory" or "sqlite"
    checkpointer_type: str = "memory"

    # SQLite path for persistent checkpointing (if using sqlite)
    sqlite_path: str = "./agent_checkpoints.db"


@dataclass
class LearnerSimulatorConfig:
    """Configuration for the learner simulator."""

    # Probability of understanding correctly (0.0 to 1.0)
    comprehension_rate: float = 0.6

    # Probability of making common mistakes
    mistake_rate: float = 0.4

    # Probability of asking clarifying questions
    question_rate: float = 0.5

    # Probability of expressing confusion
    confusion_rate: float = 0.3

    # Language proficiency level (affects grammar/vocabulary)
    english_proficiency: str = "intermediate"  # basic, intermediate, advanced

    # Background knowledge areas
    prior_knowledge: list[str] = field(default_factory=lambda: ["basic_sql"])


@dataclass
class SimulationConfig:
    """Configuration for running simulations."""

    # Maximum turns in a simulation
    max_turns: int = 30

    # Delay between turns (seconds) - for readable output
    turn_delay: float = 0.5

    # Whether to save conversation logs
    save_logs: bool = True

    # Log directory
    log_dir: str = "./simulation_logs"

    # Verbosity level: 0=quiet, 1=normal, 2=verbose
    verbosity: int = 1


@dataclass
class Config:
    """Main configuration container."""

    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    learner_sim: LearnerSimulatorConfig = field(default_factory=LearnerSimulatorConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    # Database URL (from environment or default)
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev",
        )
    )


# Global default configuration
default_config = Config()


def get_config() -> Config:
    """Get the default configuration."""
    return default_config


def create_config(**overrides) -> Config:
    """
    Create a configuration with custom overrides.

    Usage:
        config = create_config(
            model=ModelConfig(tutor_model="claude-sonnet-4-20250514"),
            simulation=SimulationConfig(max_turns=50)
        )
    """
    config = Config()

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config
