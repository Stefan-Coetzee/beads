"""
Tests for the Socratic Learning Agent.

These tests verify:
1. Tool creation and binding
2. State management
3. Graph compilation
4. Prompt generation
5. Environment configuration
"""

import os

import pytest
from langchain_core.messages import HumanMessage

from agent.config import Config, get_config
from agent.graph import create_agent, create_graph
from agent.prompts import SYSTEM_PROMPT, build_system_prompt
from agent.state import AgentState, LearnerProgress, TaskContext
from agent.tools import create_tools, get_tool_descriptions


# All tools that should be available
EXPECTED_TOOLS = {
    "get_ready",
    "show_task",
    "get_context",
    "start_task",
    "submit",
    "add_comment",
    "get_comments",
    "go_back",
    "request_help",
}


class TestToolCreation:
    """Test tool creation and configuration."""

    @pytest.mark.asyncio
    async def test_create_tools_returns_all_tools(self, async_session):
        """Test that create_tools returns all expected tools."""
        tools = create_tools(
            session=async_session,
            learner_id="test-learner",
            project_id="test-project",
        )

        assert len(tools) == 9

        tool_names = {t.name for t in tools}
        expected_names = {
            "get_ready",
            "show_task",
            "get_context",
            "start_task",
            "submit",
            "add_comment",
            "get_comments",
            "go_back",
            "request_help",
        }
        assert tool_names == expected_names

    @pytest.mark.asyncio
    async def test_tools_have_descriptions(self, async_session):
        """Test that all tools have descriptions."""
        tools = create_tools(
            session=async_session,
            learner_id="test-learner",
            project_id="test-project",
        )

        for tool in tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"

    def test_get_tool_descriptions(self):
        """Test that tool descriptions are formatted correctly."""
        descriptions = get_tool_descriptions()

        assert "## Available Tools" in descriptions
        assert "get_ready" in descriptions
        assert "submit" in descriptions
        assert "Navigation" in descriptions
        assert "Progress" in descriptions


class TestState:
    """Test agent state management."""

    def test_agent_state_creation(self):
        """Test creating an agent state."""
        state = AgentState(
            learner_id="learner-123",
            project_id="proj-abc",
        )

        assert state.learner_id == "learner-123"
        assert state.project_id == "proj-abc"
        assert state.messages == []
        assert state.current_task is None
        assert state.progress is None

    def test_agent_state_with_task_context(self):
        """Test agent state with task context."""
        task = TaskContext(
            task_id="proj-abc.1.1",
            task_title="Test Task",
            task_type="task",
            status="in_progress",
            acceptance_criteria="- Complete the task",
        )

        state = AgentState(
            learner_id="learner-123",
            project_id="proj-abc",
            current_task=task,
        )

        assert state.current_task is not None
        assert state.current_task.task_id == "proj-abc.1.1"
        assert state.current_task.status == "in_progress"

    def test_agent_state_with_progress(self):
        """Test agent state with learner progress."""
        progress = LearnerProgress(
            completed=5,
            total=20,
            percentage=25.0,
            in_progress=2,
            blocked=1,
        )

        state = AgentState(
            learner_id="learner-123",
            project_id="proj-abc",
            progress=progress,
        )

        assert state.progress is not None
        assert state.progress.completed == 5
        assert state.progress.percentage == 25.0


class TestPrompts:
    """Test prompt generation."""

    def test_build_system_prompt_minimal(self):
        """Test building system prompt with minimal context."""
        prompt = build_system_prompt(project_id="proj-123")

        assert "proj-123" in prompt
        assert "Socratic" in prompt
        assert "get_ready" in prompt
        assert "submit" in prompt

    def test_build_system_prompt_with_task(self):
        """Test building system prompt with task context."""
        task = {
            "task_id": "proj-123.1.1",
            "task_title": "Learn SQL Basics",
            "task_type": "task",
            "status": "in_progress",
            "acceptance_criteria": "- Write a SELECT query\n- Filter with WHERE",
            "learning_objectives": [
                {"level": "apply", "description": "Write SQL queries"},
            ],
            "tutor_guidance": {
                "teaching_approach": "Start with simple examples",
                "hints_to_give": ["Use SELECT * first", "Try filtering one column"],
                "common_mistakes": ["Forgetting WHERE clause"],
            },
        }

        prompt = build_system_prompt(
            project_id="proj-123",
            current_task=task,
        )

        assert "Learn SQL Basics" in prompt
        assert "Write a SELECT query" in prompt
        assert "Write SQL queries" in prompt
        assert "Start with simple examples" in prompt
        assert "Use SELECT * first" in prompt

    def test_build_system_prompt_with_progress(self):
        """Test building system prompt with progress context."""
        progress = {
            "completed": 10,
            "total": 40,
            "percentage": 25.0,
            "in_progress": 3,
            "blocked": 2,
        }

        prompt = build_system_prompt(
            project_id="proj-123",
            progress=progress,
        )

        assert "10/40" in prompt
        assert "25.0%" in prompt


class TestGraph:
    """Test graph creation and structure."""

    def test_create_graph_has_nodes(self):
        """Test that the graph has expected nodes."""
        workflow = create_graph()

        # Check nodes exist
        nodes = workflow.nodes
        assert "agent" in nodes
        assert "tools" in nodes

    def test_create_graph_compiles(self):
        """Test that the graph compiles without errors."""
        from langgraph.checkpoint.memory import MemorySaver

        workflow = create_graph()
        checkpointer = MemorySaver()

        # Should compile without errors
        graph = workflow.compile(checkpointer=checkpointer)
        assert graph is not None


class TestToolsInPrompt:
    """Test that all tools are documented in the system prompt."""

    def test_all_tools_mentioned_in_prompt(self):
        """Verify every tool is mentioned in the system prompt."""
        for tool_name in EXPECTED_TOOLS:
            assert tool_name in SYSTEM_PROMPT, (
                f"Tool '{tool_name}' is not mentioned in SYSTEM_PROMPT"
            )

    def test_prompt_tool_descriptions_complete(self):
        """Verify prompt has descriptions for all tools."""
        # Each tool should have a description line like "- **tool_name**: description"
        for tool_name in EXPECTED_TOOLS:
            pattern = f"**{tool_name}**:"
            assert pattern in SYSTEM_PROMPT, (
                f"Tool '{tool_name}' missing description in prompt (expected '{pattern}')"
            )

    def test_tool_count_matches_prompt(self):
        """Verify the number of tools matches what's in the prompt."""
        # Count tool mentions in the "Your Toolset" section
        tool_section_start = SYSTEM_PROMPT.find("## Your Toolset")
        tool_section_end = SYSTEM_PROMPT.find("## Workflow Guidelines")
        tool_section = SYSTEM_PROMPT[tool_section_start:tool_section_end]

        # Count "- **" patterns which indicate tool entries
        tool_count = tool_section.count("- **")
        assert tool_count == len(EXPECTED_TOOLS), (
            f"Prompt has {tool_count} tools but expected {len(EXPECTED_TOOLS)}"
        )


class TestToolsMounted:
    """Test that tools are properly mounted to the agent."""

    @pytest.mark.asyncio
    async def test_agent_has_all_tools_mounted(self, async_session):
        """Verify agent has all expected tools mounted."""
        agent = create_agent(
            learner_id="test-learner",
            project_id="test-project",
            session=async_session,
        )

        # Get tool names from the agent
        mounted_tools = {tool.name for tool in agent.tools}

        assert mounted_tools == EXPECTED_TOOLS, (
            f"Mounted tools {mounted_tools} don't match expected {EXPECTED_TOOLS}"
        )

    @pytest.mark.asyncio
    async def test_tools_are_callable(self, async_session):
        """Verify all mounted tools are callable."""
        tools = create_tools(
            session=async_session,
            learner_id="test-learner",
            project_id="test-project",
        )

        for tool in tools:
            assert callable(tool.coroutine), f"Tool {tool.name} is not callable"
            assert hasattr(tool, "ainvoke"), f"Tool {tool.name} missing ainvoke method"

    @pytest.mark.asyncio
    async def test_tools_have_schemas(self, async_session):
        """Verify all tools have proper input schemas."""
        tools = create_tools(
            session=async_session,
            learner_id="test-learner",
            project_id="test-project",
        )

        for tool in tools:
            assert tool.args_schema is not None, (
                f"Tool {tool.name} missing args_schema"
            )


class TestEnvironmentConfig:
    """Test environment and configuration setup."""

    def test_config_has_model_settings(self):
        """Verify config has required model settings."""
        config = get_config()

        assert config.model.tutor_model, "Missing tutor_model in config"
        assert config.model.learner_model, "Missing learner_model in config"
        assert config.model.tutor_temperature >= 0, "Invalid tutor_temperature"
        assert config.model.max_tokens > 0, "Invalid max_tokens"

    def test_config_uses_haiku_by_default(self):
        """Verify default model is claude-haiku-4-5."""
        config = get_config()

        assert "haiku" in config.model.tutor_model.lower(), (
            f"Default tutor model should be haiku, got {config.model.tutor_model}"
        )
        assert "haiku" in config.model.learner_model.lower(), (
            f"Default learner model should be haiku, got {config.model.learner_model}"
        )

    def test_anthropic_api_key_documented(self):
        """Document that ANTHROPIC_API_KEY is required."""
        # This test documents the requirement - actual key check happens at runtime
        # The key should be set in the environment for the agent to work
        required_env_vars = ["ANTHROPIC_API_KEY"]

        for var in required_env_vars:
            # We don't fail if not set (CI might not have it)
            # but we document it's needed
            if var not in os.environ:
                pytest.skip(f"{var} not set - required for live agent testing")

    def test_database_url_has_default(self):
        """Verify DATABASE_URL has a sensible default."""
        config = get_config()

        assert config.database_url, "Missing database_url in config"
        assert "postgresql" in config.database_url, (
            "database_url should be a PostgreSQL URL"
        )
