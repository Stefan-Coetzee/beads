"""
Agent management for the API.

Manages agent instances per learner/project combination.
Agents are created lazily and cached for reuse.
"""

from typing import Dict
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from agent.graph import create_agent, AgentWrapper
from agent.config import get_config


class AgentManager:
    """
    Manages agent instances.

    Caches agents by (learner_id, project_id) for reuse across requests.
    """

    def __init__(self):
        self._agents: Dict[str, AgentWrapper] = {}

    def get_or_create(
        self,
        learner_id: str,
        project_id: str,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> AgentWrapper:
        """
        Get an existing agent or create a new one.

        Args:
            learner_id: The learner's ID
            project_id: The project ID
            session_factory: Database session factory

        Returns:
            AgentWrapper instance
        """
        key = f"{learner_id}:{project_id}"

        if key not in self._agents:
            self._agents[key] = create_agent(
                learner_id=learner_id,
                project_id=project_id,
                session_factory=session_factory,
                config=get_config(),
            )

        return self._agents[key]

    def remove(self, learner_id: str, project_id: str) -> bool:
        """Remove an agent from the cache."""
        key = f"{learner_id}:{project_id}"
        if key in self._agents:
            del self._agents[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached agents."""
        self._agents.clear()


# Global agent manager
_agent_manager = AgentManager()


def get_or_create_agent(
    learner_id: str,
    project_id: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> AgentWrapper:
    """
    Get or create an agent for the learner/project.

    This is the main entry point for getting agents in the API.
    """
    return _agent_manager.get_or_create(learner_id, project_id, session_factory)


def get_agent_manager() -> AgentManager:
    """Get the global agent manager."""
    return _agent_manager
