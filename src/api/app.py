"""
FastAPI application with proper database lifecycle management.

The key insight: FastAPI maintains ONE event loop for the server's lifetime.
By initializing the database pool in the startup event, all connections
are created in that loop and pooling works correctly.
"""

from dotenv import load_dotenv

# Load .env file before any other imports that might need env vars
load_dotenv()

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_database, close_database
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    - startup: Initialize database pool IN the event loop
    - shutdown: Close database connections cleanly
    """
    # Startup: Initialize database pool in THIS event loop
    await init_database()
    print("Database pool initialized in event loop")

    yield

    # Shutdown: Close database connections
    await close_database()
    print("Database connections closed")


def get_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Socratic Learning Agent API",
        description="API for the Maji Ndogo Socratic tutoring agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router, prefix="/api/v1")

    # Health check at root
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


# Create the app instance
app = get_app()
