"""
LangGraph agent definition for the Socratic Learning Agent.

This module defines the agent graph that:
1. Receives user messages
2. Processes them with an LLM using Socratic teaching principles
3. Executes tools to interact with the Learning Task Tracker
4. Returns responses that guide learning through questioning

Supports two modes:
- ReAct agent (recommended): Uses LangGraph's prebuilt create_react_agent
- Custom graph: Legacy implementation with manual state management
"""

import json
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
# Note: create_react_agent will move to langchain.agents in LangGraph 2.0
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from agent.config import Config, get_config
from agent.prompts import build_system_prompt
from agent.state import AgentState, EpicContext, LearnerProgress, ProjectContext, TaskContext
from agent.tools import create_tools


# =============================================================================
# Model Creation
# =============================================================================


def create_model(config: Config, model_name: str | None = None) -> ChatAnthropic:
    """
    Create a ChatAnthropic model with configured settings.

    Args:
        config: Application configuration
        model_name: Optional model name override

    Returns:
        Configured ChatAnthropic instance
    """
    actual_model = model_name or config.model.tutor_model

    # Build model kwargs
    model_kwargs: dict = {
        "model": actual_model,
        "temperature": config.model.tutor_temperature,
        "max_tokens": config.model.max_tokens,
    }

    # Add extended thinking if enabled
    if config.model.thinking_enabled:
        model_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": config.model.thinking_budget_tokens,
        }

    return ChatAnthropic(**model_kwargs)


# =============================================================================
# ReAct Agent (Recommended)
# =============================================================================


def create_react_tutor_agent(
    learner_id: str,
    project_id: str,
    session: AsyncSession,
    model: ChatAnthropic,
    tools: list,
    checkpointer: MemorySaver | None = None,
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    """
    Create a ReAct agent using LangGraph's prebuilt create_react_agent.

    This is the recommended approach - simpler and handles the agent loop
    automatically.

    Args:
        learner_id: The learner's ID
        project_id: The project ID
        session: Database session for tool execution
        model: The ChatAnthropic model instance
        tools: List of tools for the agent
        checkpointer: Optional checkpointer for persistence
        system_prompt: System prompt for the agent

    Returns:
        Compiled ReAct agent graph
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build default system prompt if not provided
    if system_prompt is None:
        system_prompt = build_system_prompt(project_id=project_id)

    # Create the ReAct agent
    graph = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer,
    )

    return graph


# =============================================================================
# Custom Graph (Legacy)
# =============================================================================


async def agent_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """
    Main agent node that processes messages and decides on actions.

    This node:
    1. Builds the system prompt with current context
    2. Invokes the LLM with the conversation history
    3. Returns the LLM's response (may include tool calls)
    """
    # Get configuration
    configurable = config.get("configurable", {})
    model = configurable.get("model")
    tools = configurable.get("tools", [])

    if not model:
        raise ValueError("Model not configured. Pass model in configurable.")

    # Build system prompt with current context
    current_task_dict = None
    if state.current_task:
        current_task_dict = {
            "task_id": state.current_task.task_id,
            "task_title": state.current_task.task_title,
            "task_type": state.current_task.task_type,
            "status": state.current_task.status,
            "acceptance_criteria": state.current_task.acceptance_criteria,
            "tutor_guidance": state.current_task.tutor_guidance,
            "learning_objectives": state.current_task.learning_objectives,
        }

    progress_dict = None
    if state.progress:
        progress_dict = {
            "completed": state.progress.completed,
            "total": state.progress.total,
            "percentage": state.progress.percentage,
            "in_progress": state.progress.in_progress,
            "blocked": state.progress.blocked,
        }

    # Epic context
    epic_dict = None
    if state.current_epic:
        epic_dict = {
            "id": state.current_epic.epic_id,
            "title": state.current_epic.title,
            "description": state.current_epic.description,
        }

    system_prompt = build_system_prompt(
        project_id=state.project_id,
        narrative_context=state.project_context.narrative_context if state.project_context else None,
        project_description=state.project_context.description if state.project_context else None,
        current_epic=epic_dict,
        current_task=current_task_dict,
        progress=progress_dict,
    )

    # Prepare messages with system prompt
    messages = [SystemMessage(content=system_prompt)] + list(state.messages)

    # Bind tools to model if available
    if tools:
        model_with_tools = model.bind_tools(tools)
    else:
        model_with_tools = model

    # Invoke the model
    response = await model_with_tools.ainvoke(messages, config)

    return {"messages": [response]}


async def tool_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """
    Tool execution node that runs requested tools.

    Executes tool calls from the last AI message and returns results.
    Also updates state based on tool results (e.g., current task, progress).
    """
    configurable = config.get("configurable", {})
    tools = configurable.get("tools", [])

    if not tools:
        return {"messages": []}

    # Build tools by name lookup
    tools_by_name = {tool.name: tool for tool in tools}

    # Get the last message (should be AI with tool calls)
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    # Execute each tool call
    outputs = []
    state_updates = {}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        if tool_name not in tools_by_name:
            result = json.dumps({"error": f"Unknown tool: {tool_name}"})
        else:
            try:
                # Execute the tool
                tool = tools_by_name[tool_name]
                result = await tool.ainvoke(tool_args)

                # Update state based on tool results
                state_updates.update(_extract_state_updates(tool_name, result))
            except Exception as e:
                result = json.dumps({"error": str(e)})

        outputs.append(
            ToolMessage(
                content=result,
                name=tool_name,
                tool_call_id=tool_call["id"],
            )
        )

    # Return messages and any state updates
    return {"messages": outputs, **state_updates}


def _extract_state_updates(tool_name: str, result: str) -> dict:
    """
    Extract state updates from tool results.

    Updates current_task and progress based on tool responses.
    """
    updates = {}

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return updates

    # Update current task from show_task or start_task
    if tool_name in ("show_task", "start_task", "get_context"):
        task_data = None

        if tool_name == "show_task":
            task_data = data
        elif tool_name == "start_task" and data.get("success"):
            context = data.get("context", {})
            if context:
                current = context.get("current_task", {})
                task_data = {
                    "id": current.get("id"),
                    "title": current.get("title"),
                    "task_type": current.get("task_type"),
                    "status": current.get("status"),
                    "acceptance_criteria": context.get("acceptance_criteria"),
                    "learning_objectives": context.get("learning_objectives", []),
                }
        elif tool_name == "get_context":
            current = data.get("current_task", {})
            task_data = {
                "id": current.get("id"),
                "title": current.get("title"),
                "task_type": current.get("task_type"),
                "status": current.get("status"),
                "acceptance_criteria": data.get("acceptance_criteria"),
                "learning_objectives": data.get("learning_objectives", []),
            }

        if task_data:
            updates["current_task"] = TaskContext(
                task_id=task_data.get("id"),
                task_title=task_data.get("title"),
                task_type=task_data.get("task_type"),
                status=task_data.get("status"),
                acceptance_criteria=task_data.get("acceptance_criteria"),
                tutor_guidance=task_data.get("tutor_guidance"),
                learning_objectives=task_data.get("learning_objectives", []),
            )

    # Update progress from get_context
    if tool_name == "get_context" and "progress" in data:
        prog = data["progress"]
        updates["progress"] = LearnerProgress(
            completed=prog.get("completed", 0),
            total=prog.get("total", 0),
            percentage=prog.get("percentage", 0.0),
        )

    # Update ready tasks from get_ready
    if tool_name == "get_ready" and "tasks" in data:
        updates["ready_tasks"] = data["tasks"]

    # Store last tool result for reference
    updates["last_tool_result"] = data

    return updates


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Determine if the agent should continue to tools or end.

    Returns 'tools' if the last message has tool calls, otherwise 'end'.
    """
    if not state.messages:
        return "end"

    last_message = state.messages[-1]

    # Check if it's an AI message with tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def create_custom_graph() -> StateGraph:
    """
    Create the custom agent graph structure (legacy).

    Returns an uncompiled StateGraph that can be compiled with tools.
    """
    # Create the graph with our state
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edge from agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    return workflow


# =============================================================================
# Agent Factory
# =============================================================================


from typing import Callable
from contextlib import asynccontextmanager


def create_agent(
    learner_id: str,
    project_id: str,
    session_factory: Callable[[], AsyncSession] | None = None,
    model_name: str | None = None,
    checkpointer: MemorySaver | None = None,
    config: Config | None = None,
    *,
    session: AsyncSession | None = None,  # Deprecated, use session_factory
) -> "AgentWrapper":
    """
    Create a compiled tutor agent ready for use.

    Uses either the prebuilt ReAct agent (recommended) or custom graph
    based on config.agent.use_react_agent setting.

    Args:
        learner_id: The learner's ID
        project_id: The project ID
        session_factory: Callable that returns an async context manager for sessions.
            Required for ReAct agent mode to avoid event loop issues.
        model_name: Anthropic model to use (overrides config)
        checkpointer: Optional checkpointer for persistence
        config: Optional configuration (uses default if not provided)
        session: Deprecated. Use session_factory instead.

    Returns:
        AgentWrapper instance
    """
    if config is None:
        config = get_config()

    # Handle backwards compatibility
    if session_factory is None:
        if session is not None:
            # Wrap the existing session in a factory-like callable
            # WARNING: This may cause event loop issues with ReAct agent
            @asynccontextmanager
            async def _session_wrapper():
                yield session

            session_factory = _session_wrapper
        else:
            # Use global session factory
            from ltt.db.connection import get_session_factory

            session_factory = get_session_factory()

    # Create the model with thinking support if enabled
    model = create_model(config, model_name)

    # Create tools bound to session factory and learner
    tools = create_tools(session_factory, learner_id, project_id)

    # Create checkpointer if not provided
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Choose agent implementation based on config
    if config.agent.use_react_agent:
        # Use prebuilt ReAct agent (recommended)
        # Note: Project context is loaded at first invocation and cached
        # For now, build a minimal prompt - full context comes from tools
        system_prompt = build_system_prompt(project_id=project_id)
        graph = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt,
            checkpointer=checkpointer,
        )
    else:
        # Use custom graph (legacy)
        workflow = create_custom_graph()
        graph = workflow.compile(checkpointer=checkpointer)

    # Return a configured wrapper
    return AgentWrapper(
        graph=graph,
        model=model,
        tools=tools,
        learner_id=learner_id,
        project_id=project_id,
        session_factory=session_factory,
        config=config,
    )


class AgentWrapper:
    """
    Wrapper around the compiled graph that manages configuration.

    Provides a clean interface for invoking the agent with proper config.
    """

    def __init__(
        self,
        graph: CompiledStateGraph,
        model: ChatAnthropic,
        tools: list,
        learner_id: str,
        project_id: str,
        session_factory: Callable[[], AsyncSession],
        config: Config | None = None,
    ):
        self.graph = graph
        self.model = model
        self.tools = tools
        self.learner_id = learner_id
        self.project_id = project_id
        self.session_factory = session_factory
        self.config = config or get_config()
        self._thread_id = f"{learner_id}-{project_id}"
        self._project_context: ProjectContext | None = None
        self._current_epic: EpicContext | None = None
        self._context_loaded = False

    @property
    def use_react_agent(self) -> bool:
        """Whether using the prebuilt ReAct agent."""
        return self.config.agent.use_react_agent

    async def _load_project_context(self) -> ProjectContext | None:
        """Load project context from database (lazy loading)."""
        if self._context_loaded:
            return self._project_context

        try:
            from ltt.services.task_service import get_task

            async with self.session_factory() as session:
                project = await get_task(session, self.project_id)
                if project:
                    self._project_context = ProjectContext(
                        project_id=project.id,
                        title=project.title,
                        description=project.description,
                        narrative_context=project.narrative_context,
                    )
        except Exception:
            pass  # Project context is optional

        self._context_loaded = True
        return self._project_context

    async def _load_current_epic(self) -> EpicContext | None:
        """Load current epic context from database.

        Finds the epic containing in-progress work, or the first open epic.
        """
        try:
            from ltt.models import TaskType
            from ltt.services.task_service import get_children
            from ltt.services.progress_service import get_or_create_progress

            async with self.session_factory() as session:
                # Get all epics for this project
                children = await get_children(session, self.project_id, recursive=False)
                epics = [c for c in children if c.task_type == TaskType.EPIC]

                if not epics:
                    return None

                # Find epic with in-progress tasks first
                for epic in epics:
                    progress = await get_or_create_progress(
                        session, epic.id, self.learner_id
                    )
                    status = progress.status.value if hasattr(progress.status, "value") else progress.status
                    if status == "in_progress":
                        self._current_epic = EpicContext(
                            epic_id=epic.id,
                            title=epic.title,
                            description=epic.description,
                        )
                        return self._current_epic

                # Fall back to first open epic
                for epic in epics:
                    progress = await get_or_create_progress(
                        session, epic.id, self.learner_id
                    )
                    status = progress.status.value if hasattr(progress.status, "value") else progress.status
                    if status in ("open", "in_progress"):
                        self._current_epic = EpicContext(
                            epic_id=epic.id,
                            title=epic.title,
                            description=epic.description,
                        )
                        return self._current_epic

                # No open epics - return first one for context
                epic = epics[0]
                self._current_epic = EpicContext(
                    epic_id=epic.id,
                    title=epic.title,
                    description=epic.description,
                )
                return self._current_epic

        except Exception:
            return None  # Epic context is optional

    def _get_config(self, thread_id: str | None = None) -> RunnableConfig:
        """Get the runnable config with model and tools."""
        return {
            "configurable": {
                "model": self.model,
                "tools": self.tools,
                "thread_id": thread_id or self._thread_id,
            }
        }

    async def ainvoke(
        self,
        message: str,
        thread_id: str | None = None,
    ) -> dict:
        """
        Invoke the agent with a user message.

        Args:
            message: The user's message
            thread_id: Optional thread ID for conversation tracking

        Returns:
            The agent's response state
        """
        config = self._get_config(thread_id)

        if self.use_react_agent:
            # ReAct agent uses simpler message format
            input_state = {"messages": [{"role": "user", "content": message}]}
        else:
            # Custom graph needs full state
            project_context = await self._load_project_context()
            current_epic = await self._load_current_epic()

            input_state = {
                "learner_id": self.learner_id,
                "project_id": self.project_id,
                "messages": [HumanMessage(content=message)],
                "project_context": project_context,
                "current_epic": current_epic,
            }

        return await self.graph.ainvoke(input_state, config)

    async def astream(
        self,
        message: str,
        thread_id: str | None = None,
    ):
        """
        Stream the agent's response.

        Args:
            message: The user's message
            thread_id: Optional thread ID for conversation tracking

        Yields:
            State updates as the agent processes
        """
        config = self._get_config(thread_id)

        if self.use_react_agent:
            # ReAct agent uses simpler message format
            input_state = {"messages": [{"role": "user", "content": message}]}
        else:
            # Custom graph needs full state
            project_context = await self._load_project_context()
            current_epic = await self._load_current_epic()

            input_state = {
                "learner_id": self.learner_id,
                "project_id": self.project_id,
                "messages": [HumanMessage(content=message)],
                "project_context": project_context,
                "current_epic": current_epic,
            }

        async for event in self.graph.astream(input_state, config, stream_mode="values"):
            yield event

    def get_state(self, thread_id: str | None = None) -> dict | None:
        """Get the current state for a thread."""
        config = self._get_config(thread_id)
        try:
            return self.graph.get_state(config)
        except Exception:
            return None

    async def aget_state(self, thread_id: str | None = None) -> dict | None:
        """Get the current state for a thread (async version)."""
        config = self._get_config(thread_id)
        try:
            return await self.graph.aget_state(config)
        except Exception:
            return None


def create_agent_simple(
    learner_id: str,
    project_id: str,
    model_name: str | None = None,
    config: Config | None = None,
) -> "AgentWrapper":
    """
    Create an agent using the global session factory.

    Simple way to create an agent - just call it.
    Uses NullPool by default so no event loop issues.

    Args:
        learner_id: The learner's ID
        project_id: The project ID
        model_name: Anthropic model to use (overrides config)
        config: Optional configuration

    Returns:
        AgentWrapper ready for use

    Usage:
        agent = create_agent_simple("learner-1", "proj-1")
        response = await agent.ainvoke("Hello!")
    """
    from ltt.db.connection import get_session_factory

    return create_agent(
        learner_id=learner_id,
        project_id=project_id,
        session_factory=get_session_factory(),
        model_name=model_name,
        config=config,
    )


async def create_agent_with_context(
    learner_id: str,
    project_id: str,
    session_factory: Callable[[], AsyncSession] | None = None,
    model_name: str | None = None,
    checkpointer: MemorySaver | None = None,
    config: Config | None = None,
) -> "AgentWrapper":
    """
    Create an agent with full project context loaded.

    This async factory function loads the project context from the database
    before creating the agent, ensuring the system prompt includes:
    - Project description
    - Narrative context
    - Project content

    Args:
        learner_id: The learner's ID
        project_id: The project ID
        session_factory: Callable that returns an async context manager for sessions
        model_name: Anthropic model to use (overrides config)
        checkpointer: Optional checkpointer for persistence
        config: Optional configuration

    Returns:
        AgentWrapper with full project context

    Usage:
        agent = await create_agent_with_context("learner-1", "proj-1")
        response = await agent.ainvoke("Hello!")
    """
    if config is None:
        config = get_config()

    if session_factory is None:
        from ltt.db.connection import get_session_factory
        session_factory = get_session_factory()

    # Load project context from database
    project_description = None
    narrative_context = None
    project_content = None
    current_epic_dict = None

    try:
        from ltt.services.task_service import get_task, get_children
        from ltt.services.progress_service import get_or_create_progress

        async with session_factory() as session:
            project = await get_task(session, project_id)
            if project:
                project_description = project.description
                narrative_context = project.narrative_context
                project_content = project.content

                # Find current epic (in-progress or first open)
                children = await get_children(session, project_id, recursive=False)
                epics = [c for c in children if c.task_type == "epic"]

                for epic in epics:
                    progress = await get_or_create_progress(session, epic.id, learner_id)
                    status = progress.status.value if hasattr(progress.status, "value") else progress.status
                    if status in ("in_progress", "open"):
                        current_epic_dict = {
                            "id": epic.id,
                            "title": epic.title,
                            "description": epic.description,
                        }
                        break
    except Exception:
        pass  # Context is optional, proceed with defaults

    # Create model
    model = create_model(config, model_name)

    # Create tools
    tools = create_tools(session_factory, learner_id, project_id)

    # Create checkpointer
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build system prompt with full context
    system_prompt = build_system_prompt(
        project_id=project_id,
        narrative_context=narrative_context,
        project_description=project_description,
        project_content=project_content,
        current_epic=current_epic_dict,
    )

    # Create the graph
    if config.agent.use_react_agent:
        graph = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt,
            checkpointer=checkpointer,
        )
    else:
        workflow = create_custom_graph()
        graph = workflow.compile(checkpointer=checkpointer)

    # Return wrapper
    wrapper = AgentWrapper(
        graph=graph,
        model=model,
        tools=tools,
        learner_id=learner_id,
        project_id=project_id,
        session_factory=session_factory,
        config=config,
    )

    # Pre-populate cached context
    if project_description or narrative_context:
        wrapper._project_context = ProjectContext(
            project_id=project_id,
            title="",  # We don't store title separately
            description=project_description or "",
            narrative_context=narrative_context,
        )
        wrapper._context_loaded = True

    if current_epic_dict:
        wrapper._current_epic = EpicContext(
            epic_id=current_epic_dict["id"],
            title=current_epic_dict["title"],
            description=current_epic_dict["description"],
        )

    return wrapper
