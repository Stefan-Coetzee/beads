"""
FastAPI application with proper database lifecycle management.

The key insight: FastAPI maintains ONE event loop for the server's lifetime.
By initializing the database pool in the startup event, all connections
are created in that loop and pooling works correctly.
"""

from dotenv import load_dotenv

# Load .env file before any other imports that might need env vars
load_dotenv()

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from api.agents import close_checkpointer, init_checkpointer
from api.database import close_database, get_session_factory, init_database
from api.frontend_routes import router as frontend_router
from api.lti.routes import init_lti_storage
from api.lti.routes import router as lti_router
from api.routes import router
from api.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Default project to ingest if no projects exist
DEFAULT_PROJECT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "content"
    / "projects"
    / "DA"
    / "MN_Part1"
    / "structured"
    / "water_analysis_project.json"
)


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

    # Initialize LTI storage if Redis URL is configured
    settings = get_settings()
    if settings.redis_url:
        init_lti_storage(settings.redis_url)
        print("LTI storage initialized (Redis)")
    else:
        logger.info("LTT_REDIS_URL not set — LTI endpoints disabled")

    # Initialize agent checkpointer (PostgresSaver or MemorySaver)
    await init_checkpointer()

    # Ensure at least one project exists (local dev only)
    if settings.env == "local":
        await ensure_projects_exist()

    yield

    # Shutdown: Close checkpointer pool, then database connections
    await close_checkpointer()
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

    settings = get_settings()

    # CSP middleware for LTI iframe embedding
    class CSPMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            response.headers["Content-Security-Policy"] = (
                f"frame-ancestors {settings.csp_frame_ancestors}"
            )
            # Remove X-Frame-Options so CSP frame-ancestors takes precedence
            if "X-Frame-Options" in response.headers:
                del response.headers["X-Frame-Options"]
            return response

    app.add_middleware(CSPMiddleware)

    # CORS middleware for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router, prefix="/api/v1")
    app.include_router(frontend_router)  # Frontend routes already have /api/v1 prefix
    app.include_router(lti_router)  # LTI routes at /lti/*

    # Health check at root
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


# Create the app instance
app = get_app()
