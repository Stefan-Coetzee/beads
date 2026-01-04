"""
FastAPI application for the Socratic Learning Agent.

This provides HTTP endpoints for agent interactions with proper
database connection pooling.
"""

from api.app import app, get_app

__all__ = ["app", "get_app"]
