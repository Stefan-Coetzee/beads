"""
HTTP client for the Socratic Learning Agent API.

Provides a simple interface for interacting with the agent
via HTTP instead of direct agent calls.
"""

import json
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx


@dataclass
class ChatResponse:
    """Response from the agent."""

    response: str
    thread_id: str
    tool_calls: list[dict] | None = None


@dataclass
class StreamChunk:
    """A chunk of streamed response."""

    type: str  # 'text', 'tool_call', 'tool_result', 'done', 'error'
    content: str | dict | None


class AgentClient:
    """
    HTTP client for the Socratic Learning Agent API.

    Usage:
        async with AgentClient() as client:
            response = await client.chat(
                message="Hello!",
                learner_id="learner-1",
                project_id="proj-1"
            )
            print(response.response)
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AgentClient":
        self._client = httpx.AsyncClient(timeout=120.0)  # Long timeout for LLM calls
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with AgentClient() as client:'")
        return self._client

    async def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        message: str,
        learner_id: str,
        project_id: str,
        thread_id: str | None = None,
    ) -> ChatResponse:
        """
        Send a message to the agent and get a response.

        Args:
            message: The user's message
            learner_id: The learner's ID
            project_id: The project ID
            thread_id: Optional thread ID for conversation continuity

        Returns:
            ChatResponse with the agent's response
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/chat",
            json={
                "message": message,
                "learner_id": learner_id,
                "project_id": project_id,
                "thread_id": thread_id,
            },
        )
        response.raise_for_status()
        data = response.json()

        return ChatResponse(
            response=data["response"],
            thread_id=data["thread_id"],
            tool_calls=data.get("tool_calls"),
        )

    async def chat_stream(
        self,
        message: str,
        learner_id: str,
        project_id: str,
        thread_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Send a message and stream the response.

        Args:
            message: The user's message
            learner_id: The learner's ID
            project_id: The project ID
            thread_id: Optional thread ID

        Yields:
            StreamChunk objects as the response arrives
        """
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/v1/chat/stream",
            json={
                "message": message,
                "learner_id": learner_id,
                "project_id": project_id,
                "thread_id": thread_id,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    yield StreamChunk(
                        type=data["type"],
                        content=data.get("content"),
                    )

    async def create_session(
        self,
        learner_id: str,
        project_id: str,
    ) -> str:
        """
        Create a new agent session.

        Returns:
            Session ID
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/session",
            json={
                "learner_id": learner_id,
                "project_id": project_id,
            },
        )
        response.raise_for_status()
        return response.json()["session_id"]


# Convenience function for simple usage
async def chat(
    message: str,
    learner_id: str,
    project_id: str,
    base_url: str = "http://localhost:8000",
) -> ChatResponse:
    """
    Simple one-shot chat function.

    Usage:
        response = await chat("Hello!", "learner-1", "proj-1")
        print(response.response)
    """
    async with AgentClient(base_url) as client:
        return await client.chat(message, learner_id, project_id)
