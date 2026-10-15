"""Public HTTP safeguards; no model loading or research behavior is changed."""

import asyncio
import base64
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.backend import config
from app.backend.main import create_app
from app.backend.security import DemoAuthMiddleware


USERNAME = "reviewer"
PASSWORD = "test-only-random-password-over-24-characters"
HOST = "autovue.example.ts.net"
ORIGIN = "https://" + HOST
AUTHORIZATION = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()


def protected_app(**settings):
    app = FastAPI()

    @app.post("/api/jobs")
    async def receive_upload(request: Request):
        return {"received": len(await request.body())}

    @app.get("/status")
    def status():
        return {"status": "ok"}

    app.add_middleware(
        DemoAuthMiddleware, required=True, username=USERNAME, password=PASSWORD,
        public_mode=True, public_host=HOST, public_origin=ORIGIN,
        local_hosts=["127.0.0.1:8080", "localhost:8080"], **settings,
    )
    return app


class PublicSecurityTests(unittest.TestCase):
    def public_settings(self, **settings):
        values = dict(
            FRONTEND_DIST=None, REQUIRE_AUTH=False, AUTH_USERNAME=USERNAME,
            AUTH_PASSWORD=PASSWORD, CORS_ORIGINS=["https://evil.example"],
            PUBLIC_MODE=True, PUBLIC_HOST=HOST, PUBLIC_ORIGIN=ORIGIN,
            LOCAL_HOSTS=["127.0.0.1:8080", "localhost:8080"],
        )
        values.update(settings)
        return patch.multiple(config, **values)

    def test_public_mode_fails_closed_without_auth_host_https_and_strong_password(self):
        for values, detail in [
            ({"AUTH_PASSWORD": ""}, "secret is missing"),
            ({"PUBLIC_HOST": ""}, "PUBLIC_HOST"),
            ({"PUBLIC_ORIGIN": "http://" + HOST}, "HTTPS"),
            ({"PUBLIC_HOST": "https://" + HOST}, "PUBLIC_HOST"),
            ({"PUBLIC_ORIGIN": "https://elsewhere.ts.net"}, "PUBLIC_HOST"),
            ({"AUTH_PASSWORD": "short"}, "24 characters"),
            ({"LOCAL_HOSTS": ["evil.example"]}, "loopback"),
        ]:
            with self.subTest(values=values), self.public_settings(**values):
                with self.assertRaisesRegex(RuntimeError, detail):
                    create_app()

    def test_host_cannot_be_bypassed_with_forwarding_headers(self):
        with self.public_settings(), TestClient(create_app(), base_url=ORIGIN) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            response = client.get("/health", headers={
                "Host": "evil.example", "X-Forwarded-Host": HOST,
                "X-Forwarded-For": "127.0.0.1",
            })
            self.assertEqual(response.status_code, 400)
            self.assertEqual(client.get("/health", headers={"Host": "localhost:8080"}).status_code, 200)

    def test_upload_run_results_crops_and_video_require_auth(self):
        with self.public_settings(), TestClient(create_app(), base_url=ORIGIN) as client:
            for method, path in [
                ("POST", "/api/jobs"), ("POST", "/api/jobs/a/run"),
                ("GET", "/api/jobs/a/results"), ("GET", "/api/jobs/a/crops/a.jpg"),
                ("GET", "/api/jobs/a/video/original"), ("GET", "/docs"),
            ]:
                with self.subTest(path=path):
                    self.assertEqual(client.request(method, path).status_code, 401)
            self.assertEqual(client.get("/", auth=(USERNAME, PASSWORD)).status_code, 200)

    def test_public_mutations_require_exact_origin_even_if_cors_lists_another(self):
        with self.public_settings(), TestClient(create_app(), base_url=ORIGIN) as client:
            client.auth = (USERNAME, PASSWORD)
            for origin in ["http://" + HOST, "https://evil.example", ORIGIN + "/", "null"]:
                self.assertEqual(client.post("/api/jobs", headers={"Origin": origin}).status_code, 403)
            self.assertEqual(client.post("/api/jobs", headers={"Origin": ORIGIN}).status_code, 422)
            self.assertEqual(client.post("/api/jobs").status_code, 422)
            self.assertEqual(client.post("/api/jobs", headers={
                "Host": "localhost:8080", "Origin": "http://localhost:8080",
            }).status_code, 422)

    def test_failure_throttling_does_not_block_authenticated_progress(self):
        with TestClient(protected_app(auth_failure_limit=3), base_url=ORIGIN) as client:
            self.assertEqual(client.get("/status").status_code, 401)
            self.assertEqual(client.get("/status").status_code, 401)
            throttled = client.get("/status", headers={"X-Forwarded-For": "different-client"})
            self.assertEqual(throttled.status_code, 429)
            self.assertGreater(int(throttled.headers["retry-after"]), 0)
            self.assertEqual(client.get("/status", auth=(USERNAME, PASSWORD)).status_code, 200)

    def test_raw_size_preflight_and_chunked_stream_enforce_boundary(self):
        with TestClient(protected_app(upload_body_limit=8), base_url=ORIGIN) as client:
            client.auth = (USERNAME, PASSWORD)
            self.assertEqual(client.post("/api/jobs", content=b"12345678").json(), {"received": 8})
            for length in ["9", "9" * 5000]:
                response = client.post("/api/jobs", content=b"", headers={"Content-Length": length})
                self.assertEqual(response.status_code, 413)
            for length in ["-1", "invalid", "1.0"]:
                self.assertEqual(client.post("/api/jobs", content=b"", headers={"Content-Length": length}).status_code, 400)
            self.assertEqual(client.post("/api/jobs", content=iter([b"1234", b"56789"])).status_code, 413)
            # A rejected upload releases the slot immediately.
            self.assertEqual(client.post("/api/jobs", content=iter([b"1234", b"5678"])).status_code, 200)


class PublicSecurityAsyncTests(unittest.IsolatedAsyncioTestCase):
    def scope(self, method="POST", path="/api/jobs", authenticated=True):
        headers = [(b"host", HOST.encode())]
        if authenticated:
            headers.append((b"authorization", AUTHORIZATION.encode()))
        return {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "scheme": "https", "method": method, "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": headers, "client": ("127.0.0.1", 12345),
            "server": (HOST, 443), "root_path": "",
        }

    async def test_unauthorized_upload_does_not_read_body_or_invoke_app(self):
        async def forbidden(*args):
            self.fail("Unauthorized requests must not reach upload parsing or the application.")

        middleware = DemoAuthMiddleware(
            forbidden, required=True, username=USERNAME, password=PASSWORD,
            public_mode=True, public_host=HOST, public_origin=ORIGIN,
        )
        messages = []

        async def send(message):
            messages.append(message)

        await middleware(self.scope(authenticated=False), forbidden, send)
        self.assertEqual(messages[0]["status"], 401)

    async def test_upload_slot_does_not_block_progress_and_is_released(self):
        waiting = asyncio.Event()
        release = asyncio.Event()

        async def app(scope, receive, send):
            if scope["method"] == "POST":
                await receive()
            await JSONResponse({"status": "ok"})(scope, receive, send)

        middleware = DemoAuthMiddleware(
            app, required=True, username=USERNAME, password=PASSWORD,
            public_mode=True, public_host=HOST, public_origin=ORIGIN,
        )
        messages = []

        async def send(message):
            messages.append(message)

        async def first_receive():
            waiting.set()
            await release.wait()
            return {"type": "http.request", "body": b"", "more_body": False}

        async def immediate_receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        first = asyncio.create_task(middleware(self.scope(), first_receive, send))
        await waiting.wait()
        await middleware(self.scope(), immediate_receive, send)
        self.assertEqual(messages[0]["status"], 429)
        await middleware(self.scope("GET", "/status"), immediate_receive, send)
        self.assertEqual(messages[2]["status"], 200)
        release.set()
        await first
        self.assertFalse(middleware.upload_busy)

    async def test_stalled_upload_times_out_and_releases_slot(self):
        app = protected_app(upload_idle_seconds=0.01)
        messages = []

        async def send(message):
            messages.append(message)

        async def stalled_receive():
            await asyncio.sleep(1)
            return {"type": "http.request", "body": b"", "more_body": False}

        await app(self.scope(), stalled_receive, send)
        self.assertEqual(messages[0]["status"], 408)


if __name__ == "__main__":
    unittest.main()
