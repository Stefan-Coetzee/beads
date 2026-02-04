"""
Simulation module for running tutor-learner conversations.

This module provides tools for simulating conversations between
the Socratic tutor agent and the learner simulator.
"""

from simulation.runner import ConversationRunner, run_simulation

__all__ = [
    "ConversationRunner",
    "run_simulation",
]
