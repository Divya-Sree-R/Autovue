"""Deployment boundary checks; these never execute or change the research pipeline."""

import base64
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.backend import config
from app.backend.main import _frontend_file, create_app


class BackendWebTests(unittest.TestCase):
    def app_settings(self, **values):
        defaults = {
            "FRONTEND_DIST": None,
            "REQUIRE_AUTH": False,
            "AUTH_USERNAME": "",
            "AUTH_PASSWORD": "",
            "CORS_ORIGINS": [],
        }
        defaults.update(values)
        return patch.multiple(config, **defaults)

    def auth_settings(self, **values):
        return self.app_settings(
            REQUIRE_AUTH=True, AUTH_USERNAME="demo", AUTH_PASSWORD="private-test-password", **values
        )

    def test_local_root_and_health_keep_existing_behavior(self):
        with self.app_settings(), TestClient(create_app()) as client:
            self.assertEqual(client.get("/").json()["service"], "AutoVue API")
            self.assertEqual(client.get("/health").json()["status"], "ok")

    def test_missing_secret_fails_at_app_construction(self):
        with self.app_settings(REQUIRE_AUTH=True):
            with self.assertRaisesRegex(RuntimeError, "secret is missing"):
                create_app()

    def test_auth_protects_api_docs_and_media_health_is_public(self):
        with self.auth_settings(), TestClient(create_app()) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            for path in ["/", "/docs", "/api/jobs", "/api/jobs/x/video/original"]:
                response = client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.headers["www-authenticate"].startswith("Basic "))
            self.assertEqual(client.get("/", auth=("demo", "wrong")).status_code, 401)
            self.assertEqual(client.get("/", auth=("demo", "private-test-password")).status_code, 200)
            token = base64.b64encode(b"different:private-test-password").decode()
            self.assertEqual(client.get("/", headers={"Authorization": f"Basic {token}"}).status_code, 401)
            for malformed in ["Bearer abc", "Basic !bad!", "Basic " + "a" * 5000]:
                self.assertEqual(client.get("/", headers={"Authorization": malformed}).status_code, 401)

    def test_authenticated_browser_cross_origin_mutation_is_denied(self):
        with self.auth_settings(), TestClient(create_app()) as client:
            authentication = ("demo", "private-test-password")
            response = client.post("/api/jobs", auth=authentication, headers={"Origin": "https://evil.example"})
            self.assertEqual(response.status_code, 403)
            response = client.post("/api/jobs", auth=authentication, headers={"Sec-Fetch-Site": "cross-site"})
            self.assertEqual(response.status_code, 403)
            # Same-origin reaches existing validation, preserving the endpoint.
            response = client.post("/api/jobs", auth=authentication, headers={"Origin": "https://testserver"})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(client.post("/api/jobs", auth=authentication).status_code, 422)

    def test_frontend_serves_assets_routes_and_range_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<!doctype html><title>AutoVue</title>")
            (root / "assets").mkdir()
            (root / "assets" / "app.js").write_text("console.log('AutoVue');")
            with self.auth_settings(FRONTEND_DIST=root), TestClient(create_app()) as client:
                self.assertEqual(client.get("/").status_code, 401)
                client.auth = ("demo", "private-test-password")
                self.assertIn("AutoVue", client.get("/").text)
                self.assertIn("AutoVue", client.get("/results/a-job-id").text)
                self.assertIn("console", client.get("/assets/app.js").text)
                ranged = client.get("/assets/app.js", headers={"Range": "bytes=0-6"})
                self.assertEqual(ranged.status_code, 206)
                self.assertEqual(ranged.text, "console")
                self.assertEqual(ranged.headers["cache-control"], "private, no-store")
                for missing in ["/assets/missing.js", "/api/missing", "/health/missing", "/docs/missing"]:
                    response = client.get(missing)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("text/html", response.headers["content-type"])

    def test_frontend_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("AutoVue")
            (root / "aliased.html").symlink_to(root / "index.html")
            (root / "outside.txt").symlink_to("/etc/passwd")
            for path in ["../etc/passwd", "assets/../../etc/passwd", r"..\etc\passwd", "aliased.html", "outside.txt"]:
                with self.assertRaises(HTTPException) as rejected:
                    _frontend_file(root, path)
                self.assertEqual(rejected.exception.status_code, 404)

    def test_configuration_paths_preserve_venv_interpreters(self):
        environment = os.environ.copy()
        environment.update({
            "AUTOVUE_JOBS_ROOT": "/tmp/autovue-config-test/jobs",
            "AUTOVUE_MAIN_PYTHON": str(config.PROJECT_ROOT / ".venv" / "bin" / "python"),
            "AUTOVUE_CORS_ORIGINS": "",
        })
        code = (
            "from app.backend.config import JOBS_ROOT, MAIN_PYTHON, CORS_ORIGINS; "
            "assert str(JOBS_ROOT) == '/tmp/autovue-config-test/jobs'; "
            "assert str(MAIN_PYTHON).endswith('/.venv/bin/python'); "
            "assert CORS_ORIGINS == []"
        )
        subprocess.run([str(config.MAIN_PYTHON), "-c", code], env=environment, check=True)


if __name__ == "__main__":
    unittest.main()
