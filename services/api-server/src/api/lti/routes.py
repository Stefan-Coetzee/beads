"""
LTI 1.3 endpoints.

POST /lti/login   - OIDC-initiated login (Step 1-2)
POST /lti/launch  - JWT validation and app launch (Step 3-4)
GET  /lti/jwks    - Tool's public key set
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .adapter import FastAPIMessageLaunch, FastAPIOIDCLogin, FastAPIRequest
from .config import get_tool_config
from .storage import RedisLaunchDataStorage
from .users import get_or_create_lti_learner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lti", tags=["lti"])

# Singleton storage (initialized in app lifespan)
_launch_data_storage: RedisLaunchDataStorage | None = None


def init_lti_storage(redis_url: str = "redis://localhost:6379/0") -> None:
    """Called during FastAPI startup."""
    global _launch_data_storage
    _launch_data_storage = RedisLaunchDataStorage.from_url(redis_url)
    logger.info("LTI launch data storage initialized (Redis)")


def get_launch_data_storage() -> RedisLaunchDataStorage:
    """Get the launch data storage singleton."""
    if _launch_data_storage is None:
        raise RuntimeError(
            "LTI storage not initialized. Set LTI_REDIS_URL env var and restart."
        )
    return _launch_data_storage


def is_lti_enabled() -> bool:
    """Check if LTI storage has been initialized."""
    return _launch_data_storage is not None


def _is_secure(request: Request) -> bool:
    """Check if request is HTTPS (direct or behind proxy/ngrok)."""
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "") == "https"


async def _get_request_data(request: Request) -> dict:
    """Extract params from GET or POST request."""
    if request.method == "GET":
        return dict(request.query_params)
    form = await request.form()
    return dict(form)


def _make_request(request: Request, request_data: dict) -> FastAPIRequest:
    return FastAPIRequest(
        cookies=dict(request.cookies),
        session={},
        request_data=request_data,
        request_is_secure=_is_secure(request),
    )


@router.api_route("/login", methods=["GET", "POST"])
async def lti_login(request: Request):
    """
    OIDC-initiated login.

    Called by the platform (Open edX) when a learner clicks an LTI link.
    Validates the request and redirects to the platform's auth endpoint.
    """
    tool_conf = get_tool_config()
    storage = get_launch_data_storage()
    request_data = await _get_request_data(request)
    fastapi_request = _make_request(request, request_data)

    target_link_uri = fastapi_request.get_param("target_link_uri")
    if not target_link_uri:
        raise HTTPException(status_code=400, detail='Missing "target_link_uri" param')

    oidc_login = FastAPIOIDCLogin(
        fastapi_request,
        tool_conf,
        launch_data_storage=storage,
    )
    redirect_response = oidc_login.redirect(target_link_uri)
    logger.info("OIDC login redirect -> %s", redirect_response.headers.get("location", "N/A"))
    return redirect_response


@router.post("/launch")
async def lti_launch(request: Request):
    """
    LTI resource link launch.

    Called by the platform after OIDC auth. Receives a signed JWT (id_token),
    validates it, maps the user, and redirects to the frontend app.
    """
    tool_conf = get_tool_config()
    storage = get_launch_data_storage()
    request_data = await _get_request_data(request)
    fastapi_request = _make_request(request, request_data)

    message_launch = FastAPIMessageLaunch(
        fastapi_request,
        tool_conf,
        launch_data_storage=storage,
    )

    launch_data = message_launch.get_launch_data()
    launch_id = message_launch.get_launch_id()

    # Handle Deep Linking (instructor content selection)
    if message_launch.is_deep_link_launch():
        return _handle_deep_link(message_launch, launch_data)

    # Extract user identity
    sub = launch_data.get("sub")
    iss = launch_data.get("iss")

    # Extract context (needed before name/email fallback)
    custom = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/custom", {}
    )

    # name/email: standard JWT claims, falling back to custom param substitution.
    # Filter out un-substituted LTI variable references (e.g. "$Person.name.full")
    # which appear when the platform has variable substitution disabled.
    def _resolved(value) -> str | None:
        if value and not str(value).startswith("$"):
            return value
        return None

    email = _resolved(launch_data.get("email")) or _resolved(custom.get("user_email"))
    name = _resolved(launch_data.get("name")) or _resolved(custom.get("user_name"))

    # NRPS fallback: if name/email still missing and NRPS is available, fetch from platform
    if (not name or not email) and message_launch.has_nrps():
        try:
            import asyncio
            nrps = message_launch.get_nrps()
            members = await asyncio.to_thread(nrps.get_members)
            for member in members:
                if member.get("user_id") == sub:
                    name = name or _resolved(member.get("name")) or " ".join(
                        filter(None, [member.get("given_name"), member.get("family_name")])
                    ) or None
                    email = email or _resolved(member.get("email"))
                    logger.info("NRPS resolved name=%s email=%s for sub=%s", name, email, sub)
                    break
        except Exception as exc:
            logger.warning("NRPS lookup failed: %s", exc)

    # Map LTI user to LTT learner
    from api.database import get_session

    async with get_session() as session:
        learner_id = await get_or_create_lti_learner(
            session=session,
            lti_sub=sub,
            lti_iss=iss,
            name=name,
            email=email,
        )

    # Determine project_id from custom params
    project_id = custom.get("project_id", "")
    workspace_type = custom.get("workspace_type", "sql")

    # Store active launch mapping for grade passback
    storage.set_value(
        f"active:{learner_id}:{project_id}",
        {"launch_id": launch_id, "sub": sub},
        exp=7200,
    )

    # Store full launch data for debug introspection
    storage.set_value(
        f"launch_info:{launch_id}",
        {
            "sub": sub,
            "iss": iss,
            "email": email,
            "name": name,
            "learner_id": learner_id,
            "project_id": project_id,
            "workspace_type": workspace_type,
            "roles": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles", []),
            "context": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {}),
            "resource_link": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}),
            "tool_platform": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/tool_platform", {}),
            "ags": launch_data.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint", {}),
            "custom": custom,
            "all_keys": list(launch_data.keys()),
        },
        exp=7200,
    )

    # Log all available LTI data from the platform
    context_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
    roles_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
    resource_link = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})
    lis_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/lis", {})
    tool_platform = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/tool_platform", {})
    ags_claim = launch_data.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint", {})
    logger.info(
        "=== LTI LAUNCH DATA ===\n"
        "  Identity:      sub=%s | iss=%s | email=%s | name=%s\n"
        "  Learner:       learner_id=%s\n"
        "  Project:       project_id=%s | workspace_type=%s\n"
        "  Launch ID:     %s\n"
        "  Roles:         %s\n"
        "  Context:       id=%s | label=%s | title=%s\n"
        "  Resource Link: id=%s | title=%s\n"
        "  LIS:           person_sourcedid=%s | course_section_sourcedid=%s\n"
        "  Platform:      guid=%s | name=%s | version=%s\n"
        "  AGS endpoint:  %s | scopes=%s\n"
        "  Custom params: %s\n"
        "  All keys:      %s\n"
        "======================",
        sub, iss, email, name,
        learner_id,
        project_id, workspace_type,
        launch_id,
        roles_claim,
        context_claim.get("id"), context_claim.get("label"), context_claim.get("title"),
        resource_link.get("id"), resource_link.get("title"),
        lis_claim.get("person_sourcedid"), lis_claim.get("course_section_sourcedid"),
        tool_platform.get("guid"), tool_platform.get("name"), tool_platform.get("version"),
        ags_claim.get("lineitems"), ags_claim.get("scope"),
        custom,
        list(launch_data.keys()),
    )

    # Build frontend URL with launch context
    frontend_base = os.getenv("LTT_FRONTEND_URL", "http://localhost:3000")
    redirect_url = (
        f"{frontend_base}/workspace/{project_id}"
        f"?launch_id={launch_id}"
        f"&learnerId={learner_id}"
        f"&type={workspace_type}"
        f"&lti=1"
    )

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/debug/context")
async def lti_debug_context(request: Request):
    """
    Return full LTI launch data for the current session.
    Only available when DEBUG=true env var is set.
    """
    if not os.getenv("DEBUG"):
        raise HTTPException(status_code=404, detail="Not found")

    launch_id = request.headers.get("x-lti-launch-id")
    if not launch_id:
        return JSONResponse(content={"error": "No LTI session (missing X-LTI-Launch-Id header)"})

    storage = get_launch_data_storage()
    data = storage.get_value(f"launch_info:{launch_id}")
    if not data:
        return JSONResponse(content={"error": f"No launch data found for launch_id={launch_id}"})

    return JSONResponse(content={"launch_id": launch_id, "data": data})


@router.get("/jwks")
async def lti_jwks():
    """
    Serve the tool's public JSON Web Key Set.

    The platform fetches this to verify JWTs signed by our tool.
    """
    tool_conf = get_tool_config()
    # get_jwks() already returns {"keys": [...]}, don't double-wrap
    return JSONResponse(content=tool_conf.get_jwks())


def _handle_deep_link(message_launch, launch_data: dict):
    """
    Handle Deep Linking request from instructor.

    For MVP: returns a single resource pointing to the default project.
    TODO: Render project selection UI.
    """
    from pylti1p3.deep_link_resource import DeepLinkResource

    deep_link = message_launch.get_deep_link()

    resource = DeepLinkResource()
    resource.set_url(
        launch_data.get(
            "https://purl.imsglobal.org/spec/lti/claim/target_link_uri", ""
        )
    )
    resource.set_custom_params({"project_id": "proj-9b46"})
    resource.set_title("Maji Ndogo Water Analysis")

    html = deep_link.output_response_form([resource])
    return HTMLResponse(content=html)
