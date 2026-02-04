"""
LangGraph tool wrappers for the Learning Task Tracker tools.

These tools wrap the LTT tools module to work with LangGraph's tool calling.
Each tool is async and requires a database session and learner_id from context.
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.tools import (
    GetCommentsInput,
    GetContextInput,
    GetReadyInput,
    GoBackInput,
    RequestHelpInput,
    StartTaskInput,
    SubmitInput,
)
from ltt.tools import add_comment as ltt_add_comment
from ltt.tools import get_comments as ltt_get_comments
from ltt.tools import get_context as ltt_get_context
from ltt.tools import get_ready as ltt_get_ready
from ltt.tools import go_back as ltt_go_back
from ltt.tools import request_help as ltt_request_help
from ltt.tools import start_task as ltt_start_task
from ltt.tools import submit as ltt_submit

# =============================================================================
# Tool Input Schemas (simplified for LLM)
# =============================================================================


class GetReadyToolInput(BaseModel):
    """Get tasks that are ready to work on."""

    task_type: str | None = Field(
        None, description="Filter by task type: 'task', 'subtask', 'epic'"
    )
    limit: int = Field(5, description="Maximum number of tasks to return (1-20)", ge=1, le=20)


class GetContextToolInput(BaseModel):
    """Get full context for a task."""

    task_id: str = Field(..., description="The task ID to get context for")


class StartTaskToolInput(BaseModel):
    """Start working on a task."""

    task_id: str = Field(..., description="The task ID to start working on")


class SubmitToolInput(BaseModel):
    """Submit work for a task."""

    task_id: str = Field(..., description="The task ID to submit for")
    content: str = Field(..., description="The submission content (code, text, SQL, etc.)")
    submission_type: str = Field(
        "text",
        description="Type of submission: 'code', 'sql', 'text', 'jupyter_cell', 'result_set'",
    )


class AddCommentToolInput(BaseModel):
    """Add a comment to a task."""

    task_id: str = Field(..., description="The task ID to comment on")
    comment: str = Field(..., description="The comment text")


class GetCommentsToolInput(BaseModel):
    """Get comments on a task."""

    task_id: str = Field(..., description="The task ID to get comments for")
    limit: int = Field(10, description="Maximum comments to return", ge=1, le=50)


class GoBackToolInput(BaseModel):
    """Reopen a closed task."""

    task_id: str = Field(..., description="The closed task ID to reopen")
    reason: str = Field(..., description="Reason for reopening the task")


class RequestHelpToolInput(BaseModel):
    """Request help from an instructor."""

    task_id: str = Field(..., description="The task ID needing help")
    message: str = Field(..., description="Description of what help is needed")


# =============================================================================
# Tool Factory Functions
# =============================================================================


from typing import Callable


def create_tools(
    session_factory: Callable[[], AsyncSession],
    learner_id: str,
    project_id: str,
) -> list[StructuredTool]:
    """
    Create LangGraph tools bound to a specific session factory and learner.

    Uses a session factory instead of a session instance to avoid event loop
    mismatch issues when tools are executed by create_react_agent in a
    different async context.

    Args:
        session_factory: Callable that returns a fresh AsyncSession
        learner_id: The learner's ID
        project_id: The current project ID

    Returns:
        List of StructuredTool instances ready for LangGraph
    """

    async def get_ready(task_type: str | None = None, limit: int = 5) -> str:
        """Get tasks that are unblocked and ready to work on.

        Returns a list of tasks prioritized by status (in_progress first) and priority.
        Use this to see what the learner can work on next.
        """
        async with session_factory() as session:
            input_data = GetReadyInput(project_id=project_id, task_type=task_type, limit=limit)
            result = await ltt_get_ready(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def get_context(task_id: str) -> str:
        """Get full context for a task including hierarchy and progress.

        Returns task details, project hierarchy, ready tasks list, and learner progress.
        Use this to understand where a task fits in the bigger picture.
        """
        async with session_factory() as session:
            input_data = GetContextInput(task_id=task_id)
            result = await ltt_get_context(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def start_task(task_id: str) -> str:
        """Start working on a task.

        Sets the task status to 'in_progress' and returns full context.
        Use this when the learner decides to begin work on a task.
        """
        async with session_factory() as session:
            input_data = StartTaskInput(task_id=task_id)
            result = await ltt_start_task(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def submit(task_id: str, content: str, submission_type: str = "text") -> str:
        """Submit work for a task and trigger validation.

        If validation passes, the task is automatically closed.
        Use this when the learner has completed the acceptance criteria.

        Submission types: code, sql, text, jupyter_cell, result_set
        """
        async with session_factory() as session:
            input_data = SubmitInput(task_id=task_id, content=content, submission_type=submission_type)
            result = await ltt_submit(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def add_comment(task_id: str, comment: str) -> str:
        """Add a comment or note to a task.

        Use this to record questions, observations, or progress notes.
        """
        from ltt.tools.schemas import AddCommentInput as CommentInput

        async with session_factory() as session:
            input_data = CommentInput(task_id=task_id, comment=comment)
            result = await ltt_add_comment(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def get_comments(task_id: str, limit: int = 10) -> str:
        """Get comments on a task.

        Returns both shared comments and this learner's private comments.
        """
        async with session_factory() as session:
            input_data = GetCommentsInput(task_id=task_id, limit=limit)
            result = await ltt_get_comments(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def go_back(task_id: str, reason: str) -> str:
        """Reopen a previously closed task.

        Use when the learner wants to revisit or redo a completed task.
        Requires a reason for the audit trail.
        """
        async with session_factory() as session:
            input_data = GoBackInput(task_id=task_id, reason=reason)
            result = await ltt_go_back(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def request_help(task_id: str, message: str) -> str:
        """Request help from an instructor.

        Use when the learner is stuck and needs human assistance.
        This creates a help request that instructors can review.
        """
        async with session_factory() as session:
            input_data = RequestHelpInput(task_id=task_id, message=message)
            result = await ltt_request_help(input=input_data, learner_id=learner_id, session=session)
            return result.model_dump_json(indent=2)

    async def get_stack() -> str:
        """Get information about the database and development environment.

        Returns the database type (MySQL), IDE (MySQL Workbench),
        available tables, and helpful starter queries.
        Use this to understand what tools and data are available.
        """
        import json

        stack_info = {
            "database": {
                "type": "MySQL",
                "version": "8.0",
                "database_name": "md_water_services",
                "ide": "MySQL Workbench",
            }
        }
        return json.dumps(stack_info, indent=2)

    # Import MySQL tools
    from agent.mysql_tools import create_mysql_tools

    mysql_tools = create_mysql_tools()

    # Create StructuredTool instances
    tools = [
        StructuredTool.from_function(
            coroutine=get_ready,
            name="get_ready_tasks",
            description="Get tasks that are unblocked and ready to work on. Returns prioritized list of tasks. Call ONCE at session start.",
            args_schema=GetReadyToolInput,
        ),
        StructuredTool.from_function(
            coroutine=get_context,
            name="get_context",
            description="Get full context for a task including hierarchy, progress, and related tasks. Rarely needed.",
            args_schema=GetContextToolInput,
        ),
        StructuredTool.from_function(
            coroutine=start_task,
            name="start_task",
            description="Start working on a task. Sets status to in_progress and returns full context.",
            args_schema=StartTaskToolInput,
        ),
        StructuredTool.from_function(
            coroutine=submit,
            name="submit",
            description="Submit work for validation. If validation passes, the task is automatically closed.",
            args_schema=SubmitToolInput,
        ),
        StructuredTool.from_function(
            coroutine=add_comment,
            name="add_comment",
            description="Add a comment or note to a task for tracking progress or questions.",
            args_schema=AddCommentToolInput,
        ),
        StructuredTool.from_function(
            coroutine=get_comments,
            name="get_comments",
            description="Get comments and notes on a task.",
            args_schema=GetCommentsToolInput,
        ),
        StructuredTool.from_function(
            coroutine=go_back,
            name="go_back",
            description="Reopen a previously closed task. Requires a reason.",
            args_schema=GoBackToolInput,
        ),
        StructuredTool.from_function(
            coroutine=request_help,
            name="request_help",
            description="Request help from an instructor when the learner is stuck.",
            args_schema=RequestHelpToolInput,
        ),
        StructuredTool.from_function(
            coroutine=get_stack,
            name="get_stack",
            description="Get information about the database and development environment (database type, IDE, tables).",
        ),
    ]

    # Add MySQL tools (run_sql)
    tools.extend(mysql_tools)

    return tools


def get_tool_descriptions() -> str:
    """Get formatted descriptions of all available tools."""
    descriptions = """
## Available Tools

### Navigation
- **get_ready_tasks**: Get tasks that are unblocked and ready to work on (call ONCE at session start)
- **get_context**: Get full context including hierarchy and progress (rarely needed)

### Progress
- **start_task**: Begin working on a task - sets to in_progress AND returns full context (content, acceptance criteria, tutor guidance)
- **submit**: Submit work for validation (closes task if passed, returns ready_tasks for next steps)

### Feedback
- **add_comment**: Add notes or questions to a task
- **get_comments**: Retrieve comments on a task

### Control
- **go_back**: Reopen a previously closed task
- **request_help**: Request human instructor assistance

### Database
- **run_sql**: Execute read-only SQL queries (VALIDATION ONLY - to verify learner's submitted queries)
- **get_stack**: Get information about the database and IDE environment
"""
    return descriptions
