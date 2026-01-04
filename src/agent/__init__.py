"""
Socratic Learning Agent - A LangGraph-based tutoring assistant.

This agent facilitates learner progress through structured projects using
Socratic teaching methods. It guides learners through epics, tasks, and
subtasks while maintaining pedagogical best practices.

Usage:
    from agent import create_agent, get_config

    config = get_config()
    agent = create_agent(learner_id, project_id, session, config=config)
    response = await agent.ainvoke("Hello!")
"""

from agent.config import Config, create_config, get_config
from agent.graph import AgentWrapper, create_agent, create_agent_simple
from agent.state import AgentState

__all__ = [
    # Config
    "Config",
    "create_config",
    "get_config",
    # Agent
    "create_agent",
    "create_agent_simple",
    "AgentWrapper",
    "AgentState",
]
