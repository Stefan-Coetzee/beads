"""
API routes for the Socratic Learning Agent.

Provides endpoints for:
- Chat: Send a message and get a response
- Stream: Send a message and stream the response
- Session management: Create/manage agent sessions
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.database import get_session_factory
from api.agents import get_or_create_agent, AgentManager

router = APIRouter(tags=["agent"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ChatRequest(BaseModel):
    """Request to chat with the agent."""

    message: str = Field(..., description="The user's message")
    learner_id: str = Field(..., description="The learner's ID")
    project_id: str = Field(..., description="The project ID")
    thread_id: str | None = Field(None, description="Optional thread ID for conversation continuity")


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

    learner_id: str = Field(..., description="The learner's ID")
    project_id: str = Field(..., description="The project ID")


class SessionResponse(BaseModel):
    """Response with session info."""

    session_id: str = Field(..., description="The session ID")
    learner_id: str
    project_id: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the agent and get a response.

    The agent will process the message, potentially calling tools,
    and return a complete response.
    """
    try:
        agent = get_or_create_agent(
            learner_id=request.learner_id,
            project_id=request.project_id,
            session_factory=get_session_factory(),
        )

        thread_id = request.thread_id or f"{request.learner_id}-{request.project_id}"

        # Get current message count before invoke (to identify new messages)
        current_state = await agent.aget_state(thread_id=thread_id)
        # LangGraph state has .values attribute containing the dict
        state_values = getattr(current_state, "values", {}) if current_state else {}
        prev_message_count = len(state_values.get("messages", [])) if state_values else 0

        result = await agent.ainvoke(request.message, thread_id=thread_id)

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
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Send a message and stream the response.

    Returns a stream of SSE events with response chunks.
    """

    async def generate() -> AsyncGenerator[str, None]:
        try:
            agent = get_or_create_agent(
                learner_id=request.learner_id,
                project_id=request.project_id,
                session_factory=get_session_factory(),
            )

            thread_id = request.thread_id or f"{request.learner_id}-{request.project_id}"

            async for event in agent.astream(request.message, thread_id=thread_id):
                messages = event.get("messages", [])
                if messages:
                    last_msg = messages[-1]

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
async def create_session(request: SessionRequest) -> SessionResponse:
    """
    Create a new agent session.

    This pre-initializes an agent for the learner/project combination.
    """
    agent = get_or_create_agent(
        learner_id=request.learner_id,
        project_id=request.project_id,
        session_factory=get_session_factory(),
    )

    session_id = f"{request.learner_id}-{request.project_id}"

    return SessionResponse(
        session_id=session_id,
        learner_id=request.learner_id,
        project_id=request.project_id,
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
