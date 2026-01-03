"""
Learner Simulator - A simulated learner for testing the Socratic tutor.

This module provides a simulated learner that:
- Responds to tutor prompts with varying levels of understanding
- Simulates a low English proficiency African learner
- Has basic SQL knowledge as prior background
- Shows realistic learning behaviors (confusion, questions, mistakes)

Usage:
    from learner_sim import create_learner_simulator

    learner = create_learner_simulator(config=config)
    response = await learner.respond(tutor_message)
"""

from learner_sim.simulator import LearnerSimulator, create_learner_simulator

__all__ = [
    "LearnerSimulator",
    "create_learner_simulator",
]
