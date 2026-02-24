"""
Authentication dependency for FastAPI endpoints.

Resolves learner identity from the ``X-LTI-Launch-Id`` header by looking up
the launch data stored in Redis during LTI launch.  When ``auth_enabled`` is
``False`` (local / dev), falls back to a dev learner so that the API remains
usable without a real LTI session.

Usage::

    from api.auth import LearnerContext, get_learner_context

    @router.get("/example")
    async def example(ctx: LearnerContext = Depends(get_learner_context)):
        print(ctx.learner_id, ctx.project_id)
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from api.settings import get_settings


@dataclass
class LearnerContext:
    """Resolved learner identity for the current request."""

    learner_id: str
    project_id: str | None = None
    launch_id: str | None = None
    is_instructor: bool = False
    source: str = "lti"  # "lti" | "dev"


_INSTRUCTOR_ROLE_PREFIXES = (
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Administrator",
    "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator",
)


def _check_instructor(roles: list[str]) -> bool:
    return any(any(r.startswith(p) for p in _INSTRUCTOR_ROLE_PREFIXES) for r in roles)


async def get_learner_context(request: Request) -> LearnerContext:
    """FastAPI dependency — resolve learner from ``X-LTI-Launch-Id`` header."""
    settings = get_settings()
    launch_id = request.headers.get("x-lti-launch-id")

    if launch_id:
        # Try Redis lookup
        try:
            from api.lti.routes import get_launch_data_storage

            storage = get_launch_data_storage()
            info = storage.get_value(f"launch_info:{launch_id}")
            if info:
                return LearnerContext(
                    learner_id=info["learner_id"],
                    project_id=info.get("project_id") or None,
                    launch_id=launch_id,
                    is_instructor=_check_instructor(info.get("roles", [])),
                    source="lti",
                )
        except RuntimeError:
            # LTI storage not initialized (no Redis)
            pass

        # Header present but no valid session found
        if settings.auth_enabled:
            raise HTTPException(
                status_code=401,
                detail="LTI session expired or invalid",
            )

    # No header at all
    if settings.auth_enabled:
        raise HTTPException(
            status_code=401,
            detail="Missing X-LTI-Launch-Id header",
        )

    # Dev fallback (auth_enabled=False)
    return LearnerContext(
        learner_id=settings.dev_learner_id,
        project_id=settings.dev_project_id or None,
        launch_id=None,
        source="dev",
    )
