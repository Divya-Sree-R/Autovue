"""HTTP authentication for the single-origin hosted demo.

Browsers reuse Basic credentials for fetch, images, and range video requests.
The Modal edge serves HTTPS. Credentials belong in a Modal Secret, never source.
"""

import base64
import binascii
import hashlib
import hmac
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class DemoAuthMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        required: bool,
        username: str,
        password: str,
        allowed_origins: list[str] | None = None,
    ) -> None:
        if required and not (username and password):
            raise RuntimeError("AutoVue authentication is required but its secret is missing.")
        if bool(username) != bool(password) or ":" in username:
            raise RuntimeError("AutoVue authentication requires a valid username and password.")
        self.app = app
        self.enabled = bool(username and password)
        self.username = hashlib.sha256(username.encode()).digest()
        self.password = hashlib.sha256(password.encode()).digest()
        self.allowed_origins = set(allowed_origins or [])

    def _authenticated(self, authorization: str) -> bool:
        if len(authorization) > 4096:
            return False
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            decoded = base64.b64decode(token, validate=True)
            username, separator, password = decoded.partition(b":")
            if not separator:
                return False
        except (ValueError, binascii.Error):
            return False
        # Compare fixed-length digests, including both fields on every attempt.
        user_ok = hmac.compare_digest(hashlib.sha256(username).digest(), self.username)
        password_ok = hmac.compare_digest(hashlib.sha256(password).digest(), self.password)
        return user_ok & password_ok

    def _same_origin(self, scope: Scope, headers: Headers) -> bool:
        origin = headers.get("origin")
        if origin:
            if origin in self.allowed_origins:
                return True
            try:
                parsed = urlsplit(origin)
                # HTTPS may terminate at Modal's proxy before the ASGI server.
                # Match the browser's authority, with no untrusted forwarded headers.
                return (
                    parsed.scheme in {"http", "https"}
                    and parsed.netloc.lower() == headers.get("host", "").lower()
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and parsed.username is None
                )
            except ValueError:
                return False
        # Non-browser CLI clients may omit Origin. Browser cross-site requests may not.
        return headers.get("sec-fetch-site", "none") in {"none", "same-origin"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return
        if scope.get("path") == "/health" and scope.get("method") in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if not self._authenticated(headers.get("authorization", "")):
            response = JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="AutoVue", charset="UTF-8"'},
            )
            await response(scope, receive, send)
            return
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and not self._same_origin(scope, headers):
            response = JSONResponse({"detail": "Cross-origin mutation denied."}, status_code=403)
            await response(scope, receive, send)
            return

        async def secure_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"same-origin"),
                    (b"cache-control", b"private, no-store"),
                ])
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, receive, secure_send)
