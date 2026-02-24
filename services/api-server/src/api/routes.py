"""
API routes for the Socratic Learning Agent.

Provides endpoints for:
- Chat: Send a message and get a response
- Stream: Send a message and stream the response
- Session management: Create/manage agent sessions
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from api.auth import LearnerContext, get_learner_context
from api.database import get_session_factory
from api.agents import get_or_create_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ExecutionResult(BaseModel):
    """Unified execution result for SQL queries or Python code."""

    success: bool = Field(..., description="Whether execution succeeded")
    duration: float = Field(0, description="Execution time in milliseconds")

    # For successful results
    output: str | None = Field(None, description="Text output (Python stdout, or formatted SQL result)")
    columns: list[str] | None = Field(None, description="Column names (SQL only)")
    rows: list[list] | None = Field(None, description="Result rows (SQL only)")
    row_count: int | None = Field(None, description="Number of rows returned (SQL only)")

    # For errors
    error: str | None = Field(None, description="Error message")
    error_message: str | None = Field(None, description="Short error message (Python)")
    traceback: str | None = Field(None, description="Full traceback (Python)")


class WorkspaceContext(BaseModel):
    """Context from the user's workspace (editor, results)."""

    editor_content: str | None = Field(None, description="Current code in the editor")
    results: ExecutionResult | None = Field(None, description="Execution results (SQL or Python)")
    workspace_type: str | None = Field(None, description="Type of workspace: sql, python, cybersecurity")


class ChatRequest(BaseModel):
    """Request to chat with the agent."""

    message: str = Field(..., description="The user's message")
    thread_id: str | None = Field(None, description="Optional thread ID for conversation continuity")
    context: WorkspaceContext | None = Field(None, description="Workspace context (editor, results)")


class ChatResponse(BaseModel):
    """Response from the agent."""

    response: str = Field(..., description="The agent's response text")
    thread_id: str = Field(..., description="Thread ID for continuing the conversation")
    tool_calls: list[dict] | None = Field(None, description="Tool calls made during response")


class StreamChunk(BaseModel):
    """A chunk of streamed response."""

    type: str = Field(..., description="Type: 'text', 'tool_call', 'tool_result', 'done'")
    content: str | dict | None = Field(None, description="The content of this chunk")


class SessionRequest(BaseModel):
    """Request to create a new session."""

    pass


class SessionResponse(BaseModel):
    """Response with session info."""

    session_id: str = Field(..., description="The session ID")
    learner_id: str
    project_id: str


# =============================================================================
# Context Formatting
# =============================================================================


def format_workspace_context(context: WorkspaceContext | None) -> str:
    """
    Format workspace context into a string for the LLM.

    Standardizes SQL and Python results into a readable format.
    """
    if not context:
        return ""

    parts = []
    workspace_type = context.workspace_type or "sql"

    # Add workspace type indicator
    workspace_label = {
        "sql": "SQL",
        "python": "Python",
        "cybersecurity": "Cybersecurity",
    }.get(workspace_type, workspace_type.title())
    parts.append(f"[Workspace: {workspace_label}]")

    # Add editor content if present
    if context.editor_content and context.editor_content.strip():
        lang = "sql" if workspace_type == "sql" else "python"
        parts.append(f"\n**Current Code in Editor:**\n```{lang}\n{context.editor_content.strip()}\n```")

    # Format execution results (unified for SQL and Python)
    if context.results:
        r = context.results
        duration = r.duration or 0

        if r.success:
            # SQL results with tabular data
            if r.columns and r.rows is not None:
                row_count = r.row_count or len(r.rows)
                parts.append(f"\n**Query Results** ({row_count} rows, {duration:.0f}ms):")

                if r.rows:
                    # Format as markdown table (limit to first 10 rows)
                    header = "| " + " | ".join(str(c) for c in r.columns) + " |"
                    separator = "| " + " | ".join("---" for _ in r.columns) + " |"
                    table_rows = []
                    for row in r.rows[:10]:
                        table_rows.append("| " + " | ".join(str(v) for v in row) + " |")

                    parts.append(header)
                    parts.append(separator)
                    parts.extend(table_rows)

                    if len(r.rows) > 10:
                        parts.append(f"... and {len(r.rows) - 10} more rows")
                else:
                    parts.append("(No rows returned)")

            # Text output (Python or SQL messages)
            elif r.output:
                label = "Output" if workspace_type == "python" else "Result"
                parts.append(f"\n**{label}** ({duration:.0f}ms):\n```\n{r.output}\n```")
            else:
                parts.append(f"\n**Execution completed** ({duration:.0f}ms) - No output")
        else:
            # Error handling
            error_msg = r.error_message or r.error or "Unknown error"
            parts.append(f"\n**Error** ({duration:.0f}ms): {error_msg}")

            # Include traceback if available (Python)
            if r.traceback:
                parts.append(f"```\n{r.traceback}\n```")

    return "\n".join(parts)


def build_message_with_context(message: str, context: WorkspaceContext | None) -> str:
    """
    Build the full message with workspace context prepended.
    """
    context_str = format_workspace_context(context)
    if context_str:
        return f"{context_str}\n\n**User Message:** {message}"
    return message


# =============================================================================
# Thread Tracking
# =============================================================================


async def _register_thread(thread_id: str, learner_id: str, project_id: str) -> None:
    """Upsert a record in conversation_threads so threads map to learners."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO conversation_threads (thread_id, learner_id, project_id, created_at, updated_at)
                    VALUES (:tid, :lid, :pid, now(), now())
                    ON CONFLICT (thread_id)
                    DO UPDATE SET updated_at = now()
                """),
                {"tid": thread_id, "lid": learner_id, "pid": project_id},
            )
            await session.commit()
    except Exception:
        logger.debug("Failed to register thread %s (table may not exist yet)", thread_id)


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    ctx: LearnerContext = Depends(get_learner_context),
) -> ChatResponse:
    """
    Send a message to the agent and get a response.

    The agent will process the message, potentially calling tools,
    and return a complete response.
    """
    try:
        agent = get_or_create_agent(
            learner_id=ctx.learner_id,
            project_id=ctx.project_id or "",
            session_factory=get_session_factory(),
        )

        thread_id = request.thread_id or f"{ctx.learner_id}-{ctx.project_id}"

        # Record thread → learner mapping for correlation queries
        await _register_thread(thread_id, ctx.learner_id, ctx.project_id or "")

        # Build message with workspace context (editor content, results)
        full_message = build_message_with_context(request.message, request.context)

        # Get current message count before invoke (to identify new messages)
        current_state = await agent.aget_state(thread_id=thread_id)
        # LangGraph state has .values attribute containing the dict
        state_values = getattr(current_state, "values", {}) if current_state else {}
        prev_message_count = len(state_values.get("messages", [])) if state_values else 0

        result = await agent.ainvoke(full_message, thread_id=thread_id)

        # Extract response text and tool calls from NEW messages only
        messages = result.get("messages", [])
        response_text = ""
        all_tool_calls = []

        # Only collect tool calls from messages added in this turn
        new_messages = messages[prev_message_count:] if prev_message_count < len(messages) else messages
        for msg in new_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    # Convert to dict if needed
                    if hasattr(tc, "model_dump"):
                        all_tool_calls.append(tc.model_dump())
                    elif isinstance(tc, dict):
                        all_tool_calls.append(tc)
                    else:
                        all_tool_calls.append({"name": str(tc)})

        # Get the final response text (last AI message with content, no tool calls)
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                # Skip tool messages
                if hasattr(msg, "tool_call_id"):
                    continue
                # Skip AI messages that are just tool calls
                if hasattr(msg, "tool_calls") and msg.tool_calls and not msg.content:
                    continue
                response_text = msg.content
                break

        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            tool_calls=all_tool_calls if all_tool_calls else None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    ctx: LearnerContext = Depends(get_learner_context),
) -> StreamingResponse:
    """
    Send a message and stream the response.

    Returns a stream of SSE events with response chunks.
    """
    # Build the full message with workspace context prepended
    full_message = build_message_with_context(request.message, request.context)

    # Capture ctx values for the generator closure
    learner_id = ctx.learner_id
    project_id = ctx.project_id or ""
    thread_id = request.thread_id or f"{learner_id}-{project_id}"

    # Record thread → learner mapping for correlation queries
    await _register_thread(thread_id, learner_id, project_id)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            agent = get_or_create_agent(
                learner_id=learner_id,
                project_id=project_id,
                session_factory=get_session_factory(),
            )

            # full_message and thread_id are built outside the generator
            async for event in agent.astream(full_message, thread_id=thread_id):
                messages = event.get("messages", [])
                if messages:
                    last_msg = messages[-1]

                    # Skip HumanMessages - only stream AI responses and tool results
                    # LangGraph streams ALL messages including user input
                    msg_type = getattr(last_msg, "type", None)
                    if msg_type == "human":
                        continue

                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            chunk = StreamChunk(type="tool_call", content=tool_call)
                            yield f"data: {chunk.model_dump_json()}\n\n"

                    elif hasattr(last_msg, "content") and last_msg.content:
                        # Check if it's a tool message (result)
                        if hasattr(last_msg, "name"):
                            chunk = StreamChunk(
                                type="tool_result",
                                content={"name": last_msg.name, "result": last_msg.content},
                            )
                        else:
                            chunk = StreamChunk(type="text", content=last_msg.content)
                        yield f"data: {chunk.model_dump_json()}\n\n"

            # Send done signal
            yield f"data: {StreamChunk(type='done', content=None).model_dump_json()}\n\n"

        except Exception as e:
            error_chunk = StreamChunk(type="error", content=str(e))
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    ctx: LearnerContext = Depends(get_learner_context),
) -> SessionResponse:
    """
    Create a new agent session.

    This pre-initializes an agent for the learner/project combination.
    """
    learner_id = ctx.learner_id
    project_id = ctx.project_id or ""

    agent = get_or_create_agent(
        learner_id=learner_id,
        project_id=project_id,
        session_factory=get_session_factory(),
    )

    session_id = f"{learner_id}-{project_id}"

    return SessionResponse(
        session_id=session_id,
        learner_id=learner_id,
        project_id=project_id,
    )


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get the current state of a session."""
    # Parse session_id to get learner_id and project_id
    parts = session_id.rsplit("-", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    # For now, just return the session exists
    return {"session_id": session_id, "status": "active"}
