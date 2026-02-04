"""
Agent state definition for the Socratic Learning Agent.

The state maintains:
- Conversation history (messages)
- Current learner context (learner_id, project_id)
- Current task being worked on
- Learner progress summary
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field


class ProjectContext(BaseModel):
    """Project context for the agent."""

    project_id: str
    title: str | None = None
    description: str | None = None
    narrative_context: str | None = None


class EpicContext(BaseModel):
    """Current epic context for the agent."""

    epic_id: str | None = None
    title: str | None = None
    description: str | None = None


class TaskContext(BaseModel):
    """Current task context for the agent."""

    task_id: str | None = None
    task_title: str | None = None
    task_type: str | None = None
    status: str | None = None
    acceptance_criteria: str | None = None
    tutor_guidance: dict | None = None
    learning_objectives: list[dict] = Field(default_factory=list)


class LearnerProgress(BaseModel):
    """Summary of learner's overall progress."""

    completed: int = 0
    total: int = 0
    percentage: float = 0.0
    in_progress: int = 0
    blocked: int = 0


class AgentState(BaseModel):
    """
    State for the Socratic Learning Agent.

    Maintains conversation context and learner progress information.
    """

    # Required identifiers
    learner_id: str
    project_id: str

    # Conversation history - uses add_messages reducer for proper merging
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Current context
    project_context: ProjectContext | None = None
    current_epic: EpicContext | None = None
    current_task: TaskContext | None = None
    progress: LearnerProgress | None = None

    # Ready tasks for quick reference
    ready_tasks: list[dict] = Field(default_factory=list)

    # Internal tracking
    last_tool_result: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
