"""
Admin API routes for privileged operations.

All endpoints require the ``X-Admin-API-Key`` header matching
``LTT_ADMIN_API_KEY``.

Endpoints:
- POST /api/v1/projects/ingest  — ingest a project from JSON
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth import require_admin
from api.database import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


# =============================================================================
# Response / request models
# =============================================================================


class IngestResponse(BaseModel):
    """Successful ingestion response."""

    project_id: str = Field(..., description="Author-defined stable slug")
    internal_id: str = Field(..., description="Auto-generated internal ID (proj-XXXX)")
    version: int
    title: str
    task_count: int
    objective_count: int
    warnings: list[str] = []


class IngestDryRunResponse(BaseModel):
    """Dry-run validation response (no data persisted)."""

    valid: bool
    task_count: int
    objective_count: int
    errors: list[str] = []


class IngestErrorResponse(BaseModel):
    """Structured validation error response."""

    detail: str
    errors: list[str]


# =============================================================================
# Endpoints
# =============================================================================


def _error_422(detail: str, errors: list[str]):
    raise HTTPException(status_code=422, detail={"detail": detail, "errors": errors})


@router.post(
    "/projects/ingest",
    response_model=IngestResponse | IngestDryRunResponse,
    responses={
        422: {"model": IngestErrorResponse, "description": "Validation errors"},
    },
)
async def ingest_project(
    request: Request,
    dry_run: bool = Query(default=False, description="Validate without persisting"),
) -> IngestResponse | IngestDryRunResponse:
    """
    Ingest a project from JSON.

    Accepts either:
    - ``application/json`` body with the project structure
    - ``multipart/form-data`` with a ``file`` field containing the JSON

    Use ``?dry_run=true`` to validate without touching the database.
    """
    from ltt.services.ingest import (
        IngestResult,
        ingest_project_data,
        validate_project_structure,
    )
    from ltt.services.task_service import get_project_by_slug

    # ── Parse input from request ─────────────────────────────────────────
    content_type = request.headers.get("content-type", "")
    data: dict | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            _error_422(
                "No file field in multipart form",
                ["Upload a file with field name 'file'"],
            )
        try:
            raw = await upload.read()
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _error_422("Invalid JSON in uploaded file", [str(exc)])
    else:
        # Assume JSON body
        try:
            body = await request.body()
            if not body:
                _error_422(
                    "No project data provided",
                    [
                        "Send a JSON body (Content-Type: application/json) "
                        "or upload a file (Content-Type: multipart/form-data, field name 'file')"
                    ],
                )
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            _error_422("Invalid JSON body", [str(exc)])

    if not isinstance(data, dict):
        _error_422(
            "Project data must be a JSON object",
            [f"Got {type(data).__name__} instead of object"],
        )

    # ── Dry-run: validate only ───────────────────────────────────────────
    if dry_run:
        errors = validate_project_structure(data, require_slug=True)

        # Also check duplicate slug
        slug = data.get("project_id")
        version = data.get("version", 1)
        if slug and not errors:
            session_factory = get_session_factory()
            async with session_factory() as session:
                existing = await get_project_by_slug(session, slug, version)
                if existing:
                    errors.append(
                        f"Project '{slug}' version {version} already exists "
                        f"(internal ID: {existing.id}). "
                        f"Bump the version number to create a new version."
                    )
                else:
                    latest = await get_project_by_slug(session, slug)
                    if latest and version <= latest.version:
                        errors.append(
                            f"Project '{slug}' already has version {latest.version}. "
                            f"New version must be higher (got {version})."
                        )

        from ltt.services.ingest import count_objectives, count_tasks

        return IngestDryRunResponse(
            valid=len(errors) == 0,
            task_count=count_tasks(data) if not errors else 0,
            objective_count=count_objectives(data) if not errors else 0,
            errors=errors,
        )

    # ── Auto-version: if slug exists, bump to latest + 1 ────────────────
    slug = data.get("project_id")
    if slug:
        session_factory = get_session_factory()
        async with session_factory() as session:
            latest = await get_project_by_slug(session, slug)
            if latest:
                next_version = latest.version + 1
                data["version"] = next_version
                logger.info(
                    "Project '%s' exists at version %d — auto-setting version to %d",
                    slug, latest.version, next_version,
                )

    # ── Full ingestion ───────────────────────────────────────────────────
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            result: IngestResult = await ingest_project_data(
                session, data, dry_run=False, use_llm_summaries=False, require_slug=True
            )
            await session.commit()
        except ValueError as exc:
            # Structured validation / duplicate errors from ingest
            error_msg = str(exc)
            errors = error_msg.split("; ") if "; " in error_msg else [error_msg]
            _error_422("Project validation failed", errors)
        except Exception as exc:
            await session.rollback()
            logger.exception("Unexpected error during project ingestion")
            raise HTTPException(status_code=500, detail=str(exc))

    # Look up the created project to get title + version for response
    async with session_factory() as session:
        from ltt.services.task_service import get_task

        project = await get_task(session, result.project_id)

    return IngestResponse(
        project_id=project.project_slug or "",
        internal_id=project.id,
        version=project.version,
        title=project.title,
        task_count=result.task_count,
        objective_count=result.objective_count,
        warnings=result.errors,
    )
