"""
Learner Simulator implementation.

A LangGraph-based agent that simulates a learner interacting with the tutor.
"""

import json
import os
from contextlib import contextmanager
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from agent.config import Config, get_config
from agent.mysql_tools import create_learner_mysql_tools
from learner_sim.prompts import LEARNER_GREETING, build_learner_prompt


@contextmanager
def disable_tracing():
    """Temporarily disable LangSmith tracing."""
    old_value = os.environ.get("LANGSMITH_TRACING")
    os.environ["LANGSMITH_TRACING"] = "false"
    try:
        yield
    finally:
        if old_value is not None:
            os.environ["LANGSMITH_TRACING"] = old_value
        else:
            os.environ.pop("LANGSMITH_TRACING", None)


class LearnerState(BaseModel):
    """State for the learner simulator."""

    # Conversation history
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Tracking
    turn_count: int = 0
    tasks_attempted: int = 0
    tasks_completed: int = 0
    current_understanding: str = "neutral"  # confused, neutral, understanding

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def learner_node(state: LearnerState, config: RunnableConfig) -> dict:
    """
    Main learner node that generates responses to tutor messages.
    """
    configurable = config.get("configurable", {})
    model = configurable.get("model")
    system_prompt = configurable.get("system_prompt", "")
    tools = configurable.get("tools", [])

    if not model:
        raise ValueError("Model not configured.")

    # Bind tools if available
    if tools:
        model = model.bind_tools(tools)

    # Build messages
    messages = [SystemMessage(content=system_prompt)] + list(state.messages)

    # Generate response
    response = await model.ainvoke(messages)

    return {
        "messages": [response],
        "turn_count": state.turn_count + 1,
    }


async def tool_node(state: LearnerState, config: RunnableConfig) -> dict:
    """Execute tool calls from the learner."""
    configurable = config.get("configurable", {})
    tools = configurable.get("tools", [])

    if not tools:
        return {"messages": []}

    tools_by_name = {tool.name: tool for tool in tools}

    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        if tool_name not in tools_by_name:
            result = json.dumps({"error": f"Unknown tool: {tool_name}"})
        else:
            try:
                tool = tools_by_name[tool_name]
                result = await tool.ainvoke(tool_args)
            except Exception as e:
                result = json.dumps({"error": str(e)})

        outputs.append(
            ToolMessage(
                content=result,
                name=tool_name,
                tool_call_id=tool_call["id"],
            )
        )

    return {"messages": outputs}


def should_continue(state: LearnerState) -> Literal["tools", "end"]:
    """Check if we should continue to tools or end."""
    if not state.messages:
        return "end"

    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def create_learner_graph() -> StateGraph:
    """Create the learner simulator graph with tool support."""
    workflow = StateGraph(LearnerState)
    workflow.add_node("learner", learner_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("learner")

    workflow.add_conditional_edges(
        "learner",
        should_continue,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "learner")

    return workflow


class LearnerSimulator:
    """
    Simulated learner that responds to tutor messages.

    Simulates a learner with varying comprehension, realistic mistakes,
    and authentic learning behaviors.
    """

    def __init__(
        self,
        model: ChatAnthropic,
        system_prompt: str,
        tools: list[StructuredTool] | None = None,
        checkpointer: MemorySaver | None = None,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or []

        workflow = create_learner_graph()
        self.graph = workflow.compile(checkpointer=checkpointer or MemorySaver())
        self._thread_id = "learner-sim"

    def _get_config(self, thread_id: str | None = None) -> RunnableConfig:
        """Get runnable config."""
        return {
            "configurable": {
                "model": self.model,
                "system_prompt": self.system_prompt,
                "tools": self.tools,
                "thread_id": thread_id or self._thread_id,
            }
        }

    async def respond(
        self,
        tutor_message: str,
        thread_id: str | None = None,
    ) -> str:
        """
        Generate a response to a tutor message.

        Args:
            tutor_message: The tutor's message
            thread_id: Optional thread ID for conversation tracking

        Returns:
            The learner's response text
        """
        config = self._get_config(thread_id)

        input_state = {
            "messages": [HumanMessage(content=tutor_message)],
        }

        # Disable tracing for learner - only trace the tutor agent
        with disable_tracing():
            result = await self.graph.ainvoke(input_state, config)

        # Extract the response text
        if result and result.get("messages"):
            last_message = result["messages"][-1]
            if isinstance(last_message, AIMessage):
                return last_message.content

        return ""

    async def get_greeting(self) -> str:
        """Get an initial greeting from the learner."""
        return LEARNER_GREETING

    def get_state(self, thread_id: str | None = None) -> dict | None:
        """Get current state."""
        config = self._get_config(thread_id)
        try:
            return self.graph.get_state(config)
        except Exception:
            return None


def create_learner_simulator(
    config: Config | None = None,
    model_name: str | None = None,
) -> LearnerSimulator:
    """
    Create a learner simulator with the specified configuration.

    Args:
        config: Configuration (uses default if not provided)
        model_name: Model override (uses config if not provided)

    Returns:
        Configured LearnerSimulator instance
    """
    if config is None:
        config = get_config()

    # Build the system prompt with configured behavior rates
    system_prompt = build_learner_prompt(
        comprehension_rate=config.learner_sim.comprehension_rate * 100,
        confusion_rate=config.learner_sim.confusion_rate * 100,
        mistake_rate=config.learner_sim.mistake_rate * 100,
        question_rate=config.learner_sim.question_rate * 100,
    )

    # Create the model
    actual_model = model_name or config.model.learner_model
    model = ChatAnthropic(
        model=actual_model,
        temperature=config.model.learner_temperature,
        max_tokens=config.model.max_tokens,
    )

    # Create MySQL tools for the learner (with exploration-friendly description)
    tools = create_learner_mysql_tools()

    return LearnerSimulator(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
    )
