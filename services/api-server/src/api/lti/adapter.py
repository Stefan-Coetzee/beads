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

    def get_param(self, key: str) -> str | None:
        return self._request_data.get(key)

    def get_cookie(self, key: str) -> str | None:
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

    def get_cookie(self, name: str) -> str | None:
        return self._request.get_cookie(self._get_key(name))

    def set_cookie(self, name: str, value: str | int, exp: int = 3600):
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

    def __init__(self, location: str, cookie_service: FastAPICookieService | None = None):
        super().__init__()
        self._location = location
        self._cookie_service = cookie_service

    def do_redirect(self) -> Response:
        response = RedirectResponse(url=self._location, status_code=302)
        if self._cookie_service:
            self._cookie_service.update_response(response)
        return response

    def do_js_redirect(self) -> Response:
        # JS redirect needed when cookies must be set before redirect
        # (some browsers block cookies on 302 redirects in iframes)
        html = (
            "<html><head></head><body>"
            f'<script type="text/javascript">window.location="{self._location}";</script>'
            "</body></html>"
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
        launch_data_storage: LaunchDataStorage | None = None,
    ):
        cookie_service = cookie_service or FastAPICookieService(request)
        session_service = session_service or SessionService(request)
        super().__init__(request, tool_config, session_service, cookie_service, launch_data_storage)

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
        launch_data_storage: LaunchDataStorage | None = None,
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

    def _get_request_param(self, key: str) -> str | None:
        return self._request.get_param(key)
