"""HTTP authentication and opt-in safeguards for the single-origin hosted demo.

Browsers reuse Basic credentials for fetch, images, and range video requests.
The public proxy serves HTTPS. Credentials belong in secrets, never source.
"""

import asyncio
import base64
import binascii
from collections import OrderedDict
import hashlib
import hmac
import time
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
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
        public_mode: bool = False,
        public_host: str = "",
        public_origin: str = "",
        local_hosts: list[str] | None = None,
        upload_body_limit: int = 504 * 1024 * 1024,
        upload_idle_seconds: float = 60,
        upload_total_seconds: float = 1800,
        auth_failure_limit: int = 20,
        auth_failure_window: float = 60,
    ) -> None:
        if (required or public_mode) and not (username and password):
            raise RuntimeError("AutoVue authentication is required but its secret is missing.")
        if bool(username) != bool(password) or ":" in username:
            raise RuntimeError("AutoVue authentication requires a valid username and password.")
        self.app = app
        self.enabled = bool(username and password)
        self.username = hashlib.sha256(username.encode()).digest()
        self.password = hashlib.sha256(password.encode()).digest()
        self.allowed_origins = set(allowed_origins or [])
        self.public_mode = public_mode
        self.public_host = public_host.lower()
        self.public_origin = public_origin
        self.local_hosts = set(local_hosts or [])
        if public_mode:
            self.validate_public_settings(public_host, public_origin, password, local_hosts or [])
        self.upload_body_limit = upload_body_limit
        self.upload_idle_seconds = upload_idle_seconds
        self.upload_total_seconds = upload_total_seconds
        self.upload_busy = False
        self.auth_failure_limit = auth_failure_limit
        self.auth_failure_window = auth_failure_window
        self.auth_failures: OrderedDict[str, tuple[float, int]] = OrderedDict()

    @staticmethod
    def validate_public_settings(host: str, origin: str, password: str, local_hosts: list[str]) -> None:
        def valid_authority(authority: str) -> bool:
            try:
                parsed = urlsplit("//" + authority)
                return bool(
                    authority and parsed.hostname and parsed.netloc == authority
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and parsed.username is None and parsed.password is None
                    and not any(character.isspace() for character in authority)
                    and (parsed.port is None or 1 <= parsed.port <= 65535)
                )
            except ValueError:
                return False

        try:
            parsed_origin = urlsplit(origin)
            valid_origin = (
                parsed_origin.scheme == "https" and parsed_origin.netloc.lower() == host.lower()
                and not parsed_origin.path and not parsed_origin.query and not parsed_origin.fragment
            )
        except ValueError:
            valid_origin = False
        if not valid_authority(host) or not valid_origin:
            raise RuntimeError("Public AutoVue requires an exact AUTOVUE_PUBLIC_HOST and matching HTTPS AUTOVUE_PUBLIC_ORIGIN.")
        for local_host in local_hosts:
            if not valid_authority(local_host) or urlsplit("//" + local_host).hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise RuntimeError("AUTOVUE_LOCAL_HOSTS may contain only explicit loopback authorities.")
        if len(password) < 24:
            raise RuntimeError("Public AutoVue requires a random authentication password of at least 24 characters.")

    def _record_auth_failure(self, scope: Scope) -> int | None:
        # Use the transport address, never spoofable forwarding headers. Funnel
        # may aggregate visitors at loopback; valid credentials always continue.
        client = scope.get("client")
        key = str(client[0]) if client else "unknown"
        now = time.monotonic()
        start, failures = self.auth_failures.pop(key, (now, 0))
        if now - start >= self.auth_failure_window:
            start, failures = now, 0
        failures += 1
        self.auth_failures[key] = (start, failures)
        # Bound memory even if a direct server receives many source addresses.
        while len(self.auth_failures) > 4096:
            self.auth_failures.popitem(last=False)
        if failures >= self.auth_failure_limit:
            return max(1, int(self.auth_failure_window - (now - start)) + 1)
        return None

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
            if self.public_mode:
                if headers.get("host", "").lower() == self.public_host:
                    return origin == self.public_origin
                # Explicit loopback aliases permit testing the same production
                # app locally; arbitrary CORS origins do not grant public access.
                return origin in {
                    f"{scheme}://{host}" for host in self.local_hosts for scheme in ("http", "https")
                } and urlsplit(origin).netloc.lower() == headers.get("host", "").lower()
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
        headers = Headers(scope=scope)

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

        if self.public_mode and (
            len(headers.getlist("host")) != 1
            or headers.get("host", "").lower() not in {self.public_host, *self.local_hosts}
        ):
            await JSONResponse({"detail": "Host denied."}, status_code=400)(scope, receive, secure_send)
            return
        if scope.get("path") == "/health" and scope.get("method") in {"GET", "HEAD"}:
            await self.app(scope, receive, secure_send)
            return

        if not self._authenticated(headers.get("authorization", "")):
            retry_after = self._record_auth_failure(scope) if self.public_mode else None
            response = JSONResponse(
                {"detail": "Too many failed authentication attempts." if retry_after else "Authentication required."},
                status_code=429 if retry_after else 401,
                headers={
                    "WWW-Authenticate": 'Basic realm="AutoVue", charset="UTF-8"',
                    **({"Retry-After": str(retry_after)} if retry_after else {}),
                },
            )
            await response(scope, receive, secure_send)
            return
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and not self._same_origin(scope, headers):
            response = JSONResponse({"detail": "Cross-origin mutation denied."}, status_code=403)
            await response(scope, receive, secure_send)
            return

        is_upload = scope["method"] == "POST" and scope.get("path", "").rstrip("/") == "/api/jobs"
        if not self.public_mode or not is_upload:
            await self.app(scope, receive, secure_send)
            return

        lengths = headers.getlist("content-length")
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, secure_send)
                return
            digits = lengths[0].lstrip("0") or "0"
            if len(digits) > len(str(self.upload_body_limit)) or int(digits) > self.upload_body_limit:
                await JSONResponse({"detail": "Upload request exceeds the 504 MB transport limit."}, status_code=413)(scope, receive, secure_send)
                return
        if self.upload_busy:
            await JSONResponse(
                {"detail": "Another upload is in progress. Try again after it finishes."},
                status_code=429, headers={"Retry-After": "5"},
            )(scope, receive, secure_send)
            return

        # Set the slot before the first await so concurrent requests cannot race.
        self.upload_busy = True
        bytes_received = 0
        started = time.monotonic()

        async def bounded_receive() -> dict:
            nonlocal bytes_received
            remaining = self.upload_total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise HTTPException(status_code=408, detail="Upload timed out.")
            try:
                message = await asyncio.wait_for(receive(), timeout=min(self.upload_idle_seconds, remaining))
            except asyncio.TimeoutError:
                raise HTTPException(status_code=408, detail="Upload timed out.") from None
            if message["type"] == "http.request":
                bytes_received += len(message.get("body", b""))
                if bytes_received > self.upload_body_limit:
                    raise HTTPException(status_code=413, detail="Upload request exceeds the 504 MB transport limit.")
            return message

        try:
            await self.app(scope, bounded_receive, secure_send)
        finally:
            self.upload_busy = False
