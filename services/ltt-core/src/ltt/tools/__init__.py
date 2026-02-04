"""
Agent Tools module - Runtime interface for LLM agents.

Provides stateless function calls for navigating tasks, tracking progress,
and managing submissions.

Usage:
    from ltt.tools import execute_tool, get_tool_schemas

    # Get OpenAI-compatible schemas
    schemas = get_tool_schemas()

    # Execute a tool
    result = await execute_tool("get_ready", {"project_id": "proj-123"}, learner_id, session)
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.services.dependency_service import DependencyNotFoundError
from ltt.services.progress_service import InvalidStatusTransitionError
from ltt.services.submission_service import SubmissionNotFoundError
from ltt.services.task_service import TaskNotFoundError
from ltt.services.validation_service import ValidationNotFoundError
from ltt.tools.control import go_back, request_help
from ltt.tools.feedback import add_comment, get_comments
from ltt.tools.navigation import get_context, get_ready, show_task
from ltt.tools.progress import start_task, submit
from ltt.tools.schemas import (
    AddCommentInput,
    CommentOutput,
    GetCommentsInput,
    GetCommentsOutput,
    GetContextInput,
    GetContextOutput,
    GetReadyInput,
    GetReadyOutput,
    GoBackInput,
    GoBackOutput,
    RequestHelpInput,
    RequestHelpOutput,
    ShowTaskInput,
    StartTaskInput,
    StartTaskOutput,
    SubmitInput,
    SubmitOutput,
    TaskDetailOutput,
    ToolError,
)


@dataclass
class ToolDefinition:
    """Definition of a tool for registration."""

    name: str
    description: str
    input_model: type[BaseModel] | None
    output_model: type[BaseModel]
    handler: Callable
    requires_learner: bool = True  # Most tools need learner_id


TOOLS: dict[str, ToolDefinition] = {
    "get_ready": ToolDefinition(
        name="get_ready",
        description="Get tasks that are unblocked and ready to work on (in_progress first)",
        input_model=GetReadyInput,
        output_model=GetReadyOutput,
        handler=get_ready,
    ),
    "show_task": ToolDefinition(
        name="show_task",
        description="Show detailed information about a specific task",
        input_model=ShowTaskInput,
        output_model=TaskDetailOutput,
        handler=show_task,
    ),
    "get_context": ToolDefinition(
        name="get_context",
        description="Get full context for a task (objectives, criteria, summaries)",
        input_model=GetContextInput,
        output_model=GetContextOutput,
        handler=get_context,
    ),
    "start_task": ToolDefinition(
        name="start_task",
        description="Start working on a task (sets to in_progress and returns full context)",
        input_model=StartTaskInput,
        output_model=StartTaskOutput,
        handler=start_task,
    ),
    "submit": ToolDefinition(
        name="submit",
        description="Submit work for a task and trigger validation",
        input_model=SubmitInput,
        output_model=SubmitOutput,
        handler=submit,
    ),
    "add_comment": ToolDefinition(
        name="add_comment",
        description="Add a comment to a task",
        input_model=AddCommentInput,
        output_model=CommentOutput,
        handler=add_comment,
    ),
    "get_comments": ToolDefinition(
        name="get_comments",
        description="Get comments on a task",
        input_model=GetCommentsInput,
        output_model=GetCommentsOutput,
        handler=get_comments,
    ),
    "go_back": ToolDefinition(
        name="go_back",
        description="Reopen a closed task (reason required)",
        input_model=GoBackInput,
        output_model=GoBackOutput,
        handler=go_back,
    ),
    "request_help": ToolDefinition(
        name="request_help",
        description="Request human help for a task",
        input_model=RequestHelpInput,
        output_model=RequestHelpOutput,
        handler=request_help,
    ),
}


def get_tool_schemas() -> list[dict]:
    """Get OpenAI-compatible tool schemas for function calling."""
    schemas = []
    for tool in TOOLS.values():
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_model.model_json_schema() if tool.input_model else {},
            },
        }
        schemas.append(schema)
    return schemas


ERROR_CODES = {
    "NOT_FOUND": "Resource not found",
    "INVALID_STATE": "Operation not allowed in current state",
    "VALIDATION_FAILED": "Input validation failed",
    "PERMISSION_DENIED": "Not authorized for this operation",
    "BLOCKED": "Task is blocked by dependencies",
}


async def execute_tool(
    tool_name: str, input_data: dict, learner_id: str, session: AsyncSession
) -> BaseModel:
    """
    Execute a tool with error handling.

    Note: Session management is handled by LangGraph. Tools only need learner_id.

    Args:
        tool_name: Name of the tool to execute
        input_data: Input parameters as dict
        learner_id: Learner ID for scoping
        session: Database session

    Returns:
        Tool output or ToolError on failure
    """
    if tool_name not in TOOLS:
        return ToolError(error_code="UNKNOWN_TOOL", message=f"Unknown tool: {tool_name}")

    tool = TOOLS[tool_name]

    try:
        # Parse input
        if tool.input_model:
            input_obj = tool.input_model(**input_data)
        else:
            input_obj = None

        # Execute
        result = await tool.handler(input=input_obj, learner_id=learner_id, session=session)
        return result

    except (
        TaskNotFoundError,
        SubmissionNotFoundError,
        ValidationNotFoundError,
        DependencyNotFoundError,
    ) as e:
        return ToolError(error_code="NOT_FOUND", message=str(e))
    except InvalidStatusTransitionError as e:
        return ToolError(error_code="INVALID_STATE", message=str(e))
    except ValidationError as e:
        return ToolError(
            error_code="VALIDATION_FAILED",
            message=str(e),
            details=e.errors() if hasattr(e, "errors") else None,
        )
    except Exception as e:
        return ToolError(
            error_code="INTERNAL_ERROR", message=f"An unexpected error occurred: {e!s}"
        )


__all__ = [
    # Core functions
    "execute_tool",
    "get_tool_schemas",
    "TOOLS",
    # Tool handlers
    "get_ready",
    "show_task",
    "get_context",
    "start_task",
    "submit",
    "add_comment",
    "get_comments",
    "go_back",
    "request_help",
    # Schemas
    "GetReadyInput",
    "GetReadyOutput",
    "ShowTaskInput",
    "TaskDetailOutput",
    "GetContextInput",
    "GetContextOutput",
    "StartTaskInput",
    "StartTaskOutput",
    "SubmitInput",
    "SubmitOutput",
    "AddCommentInput",
    "CommentOutput",
    "GetCommentsInput",
    "GetCommentsOutput",
    "GoBackInput",
    "GoBackOutput",
    "RequestHelpInput",
    "RequestHelpOutput",
    "ToolError",
]
