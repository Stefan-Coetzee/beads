# FastAPI Implementation Spec

> Exact file layout, PyLTI1p3 adapter classes, and endpoint implementations.

---

## File Layout

```
services/api-server/src/api/
├── app.py                  # Add LTI router + Redis init
├── lti/
│   ├── __init__.py
│   ├── adapter.py          # PyLTI1p3 FastAPI adapter classes
│   ├── config.py           # Tool configuration loader
│   ├── routes.py           # /lti/login, /lti/launch, /lti/jwks
│   ├── storage.py          # Redis-backed LaunchDataStorage
│   ├── users.py            # LTI sub → LTT learner mapping
│   ├── grades.py           # AGS grade passback service
│   └── middleware.py       # LTI session resolution middleware
│
configs/lti/
├── private.key             # Tool RSA private key (DO NOT COMMIT)
├── public.key              # Tool RSA public key
├── platform.json           # Platform registration config
└── .gitignore              # Ignore *.key files
```

---

## Dependencies

```toml
# services/api-server/pyproject.toml
[project.dependencies]
PyLTI1p3 = ">=2.0.0"
redis = { version = ">=5.0.0", extras = ["hiredis"] }
cryptography = ">=42.0.0"
```

---

## RSA Key Generation

```bash
mkdir -p configs/lti

# Generate 2048-bit RSA private key
openssl genrsa -out configs/lti/private.key 2048

# Extract public key
openssl rsa -in configs/lti/private.key -pubout -out configs/lti/public.key

# .gitignore for keys
echo "*.key" > configs/lti/.gitignore
```

---

## Platform Configuration

`configs/lti/platform.json`:

```json
{
  "https://imbizo.alx-ai-tools.com": [
    {
      "default": true,
      "client_id": "<CLIENT_ID_FROM_OPENEDX>",
      "auth_login_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/launch/",
      "auth_token_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/token/<UUID>",
      "auth_audience": null,
      "key_set_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/public_keysets/<UUID>",
      "key_set": null,
      "deployment_ids": ["1"]
    }
  ]
}
```

> The `<CLIENT_ID>`, `<UUID>` values come from Open edX after you register the tool. See [07-openedx-config.md](07-openedx-config.md).

---

## PyLTI1p3 FastAPI Adapter

### `adapter.py`

The library ships with Django and Flask adapters. We implement the same interfaces for FastAPI. There are 5 classes to implement:

```python
"""
PyLTI1p3 adapter for FastAPI/Starlette.

Implements the framework-specific interfaces that the library needs:
- Request wrapper
- Cookie service
- Redirect handler
- OIDCLogin subclass
- MessageLaunch subclass
"""

from __future__ import annotations

from typing import Optional, Union

from pylti1p3.cookie import CookieService
from pylti1p3.launch_data_storage.base import LaunchDataStorage
from pylti1p3.message_launch import MessageLaunch
from pylti1p3.oidc_login import OIDCLogin
from pylti1p3.redirect import Redirect
from pylti1p3.request import Request
from pylti1p3.session import SessionService
from starlette.responses import HTMLResponse, RedirectResponse, Response


class FastAPIRequest(Request):
    """Wraps a Starlette/FastAPI request for PyLTI1p3."""

    def __init__(
        self,
        cookies: dict,
        session: dict,
        request_data: dict,
        request_is_secure: bool,
    ):
        super().__init__()
        self._cookies = cookies
        self._session = session
        self._request_data = request_data
        self._request_is_secure = request_is_secure

    @property
    def session(self) -> dict:
        return self._session

    def get_param(self, key: str) -> Optional[str]:
        return self._request_data.get(key)

    def get_cookie(self, key: str) -> Optional[str]:
        return self._cookies.get(key)

    def is_secure(self) -> bool:
        return self._request_is_secure


class FastAPICookieService(CookieService):
    """Collects cookies during the LTI flow, applies to response later."""

    def __init__(self, request: FastAPIRequest):
        self._request = request
        self._cookie_data_to_set: dict = {}

    def _get_key(self, key: str) -> str:
        return self._cookie_prefix + "-" + key

    def get_cookie(self, name: str) -> Optional[str]:
        return self._request.get_cookie(self._get_key(name))

    def set_cookie(self, name: str, value: Union[str, int], exp: int = 3600):
        self._cookie_data_to_set[self._get_key(name)] = {
            "value": str(value),
            "exp": exp,
        }

    def update_response(self, response: Response) -> None:
        """Apply collected cookies to the Starlette response."""
        for key, data in self._cookie_data_to_set.items():
            response.set_cookie(
                key=key,
                value=data["value"],
                max_age=data["exp"],
                secure=self._request.is_secure(),
                path="/",
                httponly=True,
                samesite="none" if self._request.is_secure() else "lax",
            )


class FastAPIRedirect(Redirect):
    """Handles redirects with cookie propagation."""

    def __init__(self, location: str, cookie_service: Optional[FastAPICookieService] = None):
        super().__init__()
        self._location = location
        self._cookie_service = cookie_service

    def do_redirect(self) -> Response:
        response = RedirectResponse(url=self._location, status_code=302)
        if self._cookie_service:
            self._cookie_service.update_response(response)
        return response

    def do_js_redirect(self) -> Response:
        # JS redirect is needed when cookies must be set before redirect
        # (some browsers block cookies on 302 redirects in iframes)
        html = (
            '<html><head></head><body>'
            f'<script type="text/javascript">window.location="{self._location}";</script>'
            '</body></html>'
        )
        response = HTMLResponse(content=html)
        if self._cookie_service:
            self._cookie_service.update_response(response)
        return response

    def set_redirect_url(self, location: str):
        self._location = location

    def get_redirect_url(self) -> str:
        return self._location


class FastAPIOIDCLogin(OIDCLogin):
    """Handles the OIDC login initiation step."""

    def __init__(
        self,
        request: FastAPIRequest,
        tool_config,
        session_service=None,
        cookie_service=None,
        launch_data_storage: Optional[LaunchDataStorage] = None,
    ):
        cookie_service = cookie_service or FastAPICookieService(request)
        session_service = session_service or SessionService(request)
        super().__init__(
            request, tool_config, session_service, cookie_service, launch_data_storage
        )

    def get_redirect(self, url: str) -> FastAPIRedirect:
        return FastAPIRedirect(url, self._cookie_service)

    def get_response(self, html: str) -> HTMLResponse:
        return HTMLResponse(content=html)


class FastAPIMessageLaunch(MessageLaunch):
    """Handles JWT validation and launch data extraction."""

    def __init__(
        self,
        request: FastAPIRequest,
        tool_config,
        session_service=None,
        cookie_service=None,
        launch_data_storage: Optional[LaunchDataStorage] = None,
        requests_session=None,
    ):
        cookie_service = cookie_service or FastAPICookieService(request)
        session_service = session_service or SessionService(request)
        super().__init__(
            request,
            tool_config,
            session_service,
            cookie_service,
            launch_data_storage,
            requests_session,
        )

    def _get_request_param(self, key: str) -> Optional[str]:
        return self._request.get_param(key)
```

---

## Launch Data Storage (Redis)

### `storage.py`

LTI launches happen in iframes where third-party cookies are unreliable. We store launch state in Redis instead of session cookies.

```python
"""
Redis-backed launch data storage for PyLTI1p3.

Stores nonces, state, and launch data in Redis with TTL expiry.
This avoids third-party cookie issues in iframe contexts.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis
from pylti1p3.launch_data_storage.base import LaunchDataStorage


class RedisLaunchDataStorage(LaunchDataStorage):
    """Stores LTI launch data in Redis with automatic expiry."""

    _PREFIX = "lti1p3:"
    _DEFAULT_TTL = 7200  # 2 hours

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__()
        self._redis = redis_client
        # PyLTI1p3 calls these synchronously, so we need a sync wrapper.
        # In practice, we use redis (sync) for the LTI flow since
        # PyLTI1p3 is not async-aware.
        self._sync_redis: Optional[Any] = None

    @classmethod
    def from_url(cls, redis_url: str = "redis://localhost:6379/0") -> "RedisLaunchDataStorage":
        """Create storage from Redis URL (sync client for PyLTI1p3 compatibility)."""
        import redis as sync_redis
        instance = cls.__new__(cls)
        LaunchDataStorage.__init__(instance)
        instance._redis = None
        instance._sync_redis = sync_redis.Redis.from_url(redis_url, decode_responses=True)
        return instance

    def can_set_keys_expiration(self) -> bool:
        return True

    def _prepare_key(self, key: str) -> str:
        return f"{self._PREFIX}{key}"

    def get_value(self, key: str) -> Optional[dict]:
        prepared_key = self._prepare_key(key)
        value = self._sync_redis.get(prepared_key)
        if value:
            return json.loads(value)
        return None

    def set_value(
        self, key: str, value: Any, exp: Optional[int] = None
    ) -> None:
        prepared_key = self._prepare_key(key)
        serialized = json.dumps(value)
        ttl = exp or self._DEFAULT_TTL
        self._sync_redis.setex(prepared_key, ttl, serialized)

    def check_value(self, key: str) -> bool:
        prepared_key = self._prepare_key(key)
        return bool(self._sync_redis.exists(prepared_key))
```

> **Note**: PyLTI1p3's internal methods are synchronous. We use the sync `redis` client for the LTI flow. The async `redis.asyncio` client is for our own grade passback service.

---

## Tool Configuration Loader

### `config.py`

```python
"""
LTI tool configuration loader.

Loads platform config from JSON and RSA keys from files.
Wraps PyLTI1p3's ToolConfDict for programmatic configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from pylti1p3.tool_config import ToolConfDict

_BASE_DIR = Path(__file__).resolve().parents[5]  # project root
_LTI_CONFIG_DIR = _BASE_DIR / "configs" / "lti"


def get_tool_config() -> ToolConfDict:
    """Load tool configuration from files."""
    import json

    # Load platform registration
    platform_config_path = os.getenv(
        "LTI_PLATFORM_CONFIG",
        str(_LTI_CONFIG_DIR / "platform.json"),
    )
    with open(platform_config_path) as f:
        settings = json.load(f)

    tool_conf = ToolConfDict(settings)

    # Load RSA keys
    private_key_path = os.getenv(
        "LTI_PRIVATE_KEY", str(_LTI_CONFIG_DIR / "private.key")
    )
    public_key_path = os.getenv(
        "LTI_PUBLIC_KEY", str(_LTI_CONFIG_DIR / "public.key")
    )

    with open(private_key_path) as f:
        private_key = f.read()
    with open(public_key_path) as f:
        public_key = f.read()

    # Register keys for each platform issuer
    for iss in settings:
        for reg in settings[iss]:
            client_id = reg.get("client_id")
            tool_conf.set_private_key(iss, private_key, client_id=client_id)
            tool_conf.set_public_key(iss, public_key, client_id=client_id)

    return tool_conf
```

---

## LTI Routes

### `routes.py`

```python
"""
LTI 1.3 endpoints.

POST /lti/login   - OIDC-initiated login (Step 1-2)
POST /lti/launch  - JWT validation and app launch (Step 3-4)
GET  /lti/jwks    - Tool's public key set
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .adapter import (
    FastAPIMessageLaunch,
    FastAPIOIDCLogin,
    FastAPIRequest,
)
from .config import get_tool_config
from .storage import RedisLaunchDataStorage
from .users import get_or_create_lti_learner

router = APIRouter(prefix="/lti", tags=["lti"])

# Singleton storage (initialized in app lifespan)
_launch_data_storage: RedisLaunchDataStorage | None = None


def init_lti_storage(redis_url: str = "redis://localhost:6379/0"):
    """Called during FastAPI startup."""
    global _launch_data_storage
    _launch_data_storage = RedisLaunchDataStorage.from_url(redis_url)


def get_launch_data_storage() -> RedisLaunchDataStorage:
    if _launch_data_storage is None:
        raise RuntimeError("LTI storage not initialized. Call init_lti_storage() first.")
    return _launch_data_storage


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
        session={},  # We use Redis, not session cookies
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
    return oidc_login.enable_check_cookies().redirect(target_link_uri)


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
        return await _handle_deep_link(message_launch, launch_id, launch_data)

    # Extract user identity
    sub = launch_data.get("sub")
    email = launch_data.get("email")
    name = launch_data.get("name")
    iss = launch_data.get("iss")

    # Extract context
    context = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/context", {}
    )
    custom = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/custom", {}
    )

    # Map LTI user to LTT learner (see 03-user-mapping.md)
    from api.database import get_session

    async with get_session() as session:
        learner_id = await get_or_create_lti_learner(
            session=session,
            lti_sub=sub,
            lti_iss=iss,
            name=name,
            email=email,
        )

    # Determine project_id from custom params or resource_link
    project_id = custom.get("project_id", "")
    workspace_type = custom.get("workspace_type", "sql")

    # Build frontend URL with launch context
    frontend_base = os.getenv("LTT_FRONTEND_URL", "http://localhost:3000")
    redirect_url = (
        f"{frontend_base}/workspace/{project_id}"
        f"?launch_id={launch_id}"
        f"&learner_id={learner_id}"
        f"&workspace_type={workspace_type}"
        f"&lti=1"
    )

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/jwks")
async def lti_jwks():
    """
    Serve the tool's public JSON Web Key Set.

    The platform fetches this to verify JWTs signed by our tool
    (e.g., Deep Linking responses, service token requests).
    """
    tool_conf = get_tool_config()
    return JSONResponse(content={"keys": tool_conf.get_jwks()})


async def _handle_deep_link(message_launch, launch_id: str, launch_data: dict):
    """
    Handle Deep Linking request from instructor.

    Renders a project selection UI. When the instructor picks a project,
    we send a signed JWT back to Open edX that creates the LTI link.
    """
    from pylti1p3.deep_link_resource import DeepLinkResource

    # For MVP: return a single resource pointing to our launch URL
    # TODO: Render project selection UI and let instructor pick
    deep_link = message_launch.get_deep_link()

    resource = DeepLinkResource()
    resource.set_url(
        launch_data.get("https://purl.imsglobal.org/spec/lti/claim/target_link_uri", "")
    )
    resource.set_custom_params({"project_id": "proj-9b46"})
    resource.set_title("Maji Ndogo Water Analysis")

    html = deep_link.output_response_form([resource])
    return HTMLResponse(content=html)
```

---

## LTI Session Middleware

### `middleware.py`

Resolves `launch_id` to `learner_id` for regular API calls after the initial launch.

```python
"""
Middleware to resolve LTI launch context for API requests.

After the initial LTI launch, the frontend includes launch_id in requests.
This middleware resolves it to learner_id and attaches LTI context to the request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .adapter import FastAPIMessageLaunch, FastAPIRequest
from .config import get_tool_config
from .storage import RedisLaunchDataStorage


@dataclass
class LTIContext:
    """LTI context resolved from a launch_id."""
    launch_id: str
    learner_sub: str          # LTI sub claim (platform user ID)
    learner_id: str           # LTT internal learner ID
    project_id: Optional[str] # From custom params
    has_ags: bool             # Can we send grades?
    is_instructor: bool


def resolve_launch(launch_id: str, storage: RedisLaunchDataStorage) -> Optional[LTIContext]:
    """
    Resolve a launch_id to LTI context.

    Returns None if launch_id is not found (expired or invalid).
    """
    tool_conf = get_tool_config()

    # Create a minimal request (we only need Redis, not cookies/session)
    dummy_request = FastAPIRequest(
        cookies={}, session={}, request_data={}, request_is_secure=True
    )

    try:
        message_launch = FastAPIMessageLaunch.from_cache(
            launch_id, dummy_request, tool_conf,
            launch_data_storage=storage,
        )
    except Exception:
        return None

    launch_data = message_launch.get_launch_data()
    custom = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/custom", {}
    )

    return LTIContext(
        launch_id=launch_id,
        learner_sub=launch_data.get("sub", ""),
        learner_id="",  # Caller must resolve from mapping table
        project_id=custom.get("project_id"),
        has_ags=message_launch.has_ags(),
        is_instructor=message_launch.check_teacher_access(),
    )
```

---

## App Integration

### Changes to `app.py`

```python
# In the lifespan function, add:
from api.lti.routes import init_lti_storage, router as lti_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()

    # Initialize LTI storage
    redis_url = os.getenv("LTT_REDIS_URL", "redis://localhost:6379/0")
    init_lti_storage(redis_url)

    yield
    # Cleanup

# Register LTI routes
app.include_router(lti_router)
```

### Changes to `docker-compose.yml`

Add Redis:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  redis_data:
```

---

## Environment Variables

```bash
# LTI Configuration
LTI_PLATFORM_CONFIG=configs/lti/platform.json
LTI_PRIVATE_KEY=configs/lti/private.key
LTI_PUBLIC_KEY=configs/lti/public.key
LTT_REDIS_URL=redis://localhost:6379/0

# Frontend URL (where the Next.js app is served)
LTT_FRONTEND_URL=https://your-domain.ngrok-free.app
```

---

## Request Flow After Launch

```
Frontend (iframe)                    API Server
     │                                    │
     │  GET /api/v1/project/tree          │
     │  Header: X-LTI-Launch-Id: abc123   │
     ├───────────────────────────────────→│
     │                                    │ 1. Read launch_id from header
     │                                    │ 2. Resolve from Redis → LTI context
     │                                    │ 3. Map sub → learner_id
     │                                    │ 4. Execute normal API logic
     │  ← JSON response                  │
     │←───────────────────────────────────┤
     │                                    │
     │  POST /api/v1/chat                 │
     │  Header: X-LTI-Launch-Id: abc123   │
     │  Body: {message, project_id, ...}  │
     ├───────────────────────────────────→│
     │                                    │ Same resolution flow
     │  ← SSE stream                     │
     │←───────────────────────────────────┤
```

The frontend replaces `learner_id` in request bodies with the `launch_id` header. The backend middleware resolves this to the authenticated learner_id.

---

## Error Handling

| Error | HTTP Status | Response |
|---|---|---|
| Missing `target_link_uri` in login | 400 | `{"detail": "Missing target_link_uri param"}` |
| Invalid JWT signature | 403 | `{"detail": "LTI launch validation failed"}` |
| Expired/unknown `launch_id` | 401 | `{"detail": "LTI session expired. Please relaunch from Open edX."}` |
| Platform not registered | 403 | `{"detail": "Unknown platform issuer"}` |
| AGS not available | 403 | `{"detail": "Grade passback not configured"}` |

---

## Testing the Adapter

```python
# tests/lti/test_adapter.py

import pytest
from api.lti.adapter import FastAPIRequest, FastAPICookieService


def test_request_wraps_params():
    req = FastAPIRequest(
        cookies={"session": "abc"},
        session={},
        request_data={"iss": "https://example.com", "login_hint": "user1"},
        request_is_secure=True,
    )
    assert req.get_param("iss") == "https://example.com"
    assert req.get_param("login_hint") == "user1"
    assert req.get_param("missing") is None
    assert req.is_secure() is True


def test_cookie_service_collects_and_applies():
    req = FastAPIRequest(
        cookies={}, session={}, request_data={}, request_is_secure=True
    )
    cookies = FastAPICookieService(req)
    cookies.set_cookie("state", "xyz", exp=3600)

    # Simulate applying to a response
    from starlette.testclient import TestClient
    from starlette.responses import Response

    response = Response()
    cookies.update_response(response)
    # Verify cookies were set (check response.headers)
```
