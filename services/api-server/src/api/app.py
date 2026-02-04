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
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.database import init_database, close_database, get_session_factory
from api.routes import router
from api.frontend_routes import router as frontend_router


# Default project to ingest if no projects exist
DEFAULT_PROJECT_PATH = Path(__file__).parent.parent.parent.parent.parent / "content" / "projects" / "DA" / "MN_Part1" / "structured" / "water_analysis_project.json"


async def ensure_projects_exist() -> None:
    """Check if any projects exist, and ingest default project if not."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM tasks WHERE task_type = 'project'")
        )
        project_count = result.scalar()

        if project_count == 0:
            print("No projects found in database. Ingesting default project...")

            if DEFAULT_PROJECT_PATH.exists():
                from ltt.services.ingest import ingest_project_file

                result = await ingest_project_file(session, DEFAULT_PROJECT_PATH)
                await session.commit()

                print(f"Ingested default project: {result.project_id}")
                print(f"  Tasks created: {result.task_count}")
                print(f"  Objectives created: {result.objective_count}")
            else:
                print(f"Warning: Default project file not found at {DEFAULT_PROJECT_PATH}")
        else:
            print(f"Found {project_count} existing project(s) in database")


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

    # Ensure at least one project exists
    await ensure_projects_exist()

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
    app.include_router(frontend_router)  # Frontend routes already have /api/v1 prefix

    # Health check at root
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


# Create the app instance
app = get_app()
