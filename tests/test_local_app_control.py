"""Local control safety checks; no GPU, public tunnel or project jobs are used."""

import json
import os
from pathlib import Path
import signal
import socket
import tempfile
import unittest
from unittest.mock import patch

from deploy import local_app


class LocalAppControlTests(unittest.TestCase):
    def identity(self):
        return {
            "pid": 45678, "uid": os.getuid(), "start_ticks": "8123", "boot_id": "test-boot",
            "command": ["/test/.venv/bin/python", "-B", "-m", "uvicorn", "app.backend.main:app"],
            "process_group": 45678, "session": 45678,
        }

    def state(self):
        return {
            "process": self.identity(), "port": 8080, "url": "http://127.0.0.1:8080",
            "jobs_root": "/test/jobs", "log": "/test/app.log",
            "public_configuration": {"AUTOVUE_PUBLIC_MODE": "0", "AUTOVUE_PUBLIC_HOST": "", "AUTOVUE_PUBLIC_ORIGIN": ""},
        }

    def test_credentials_are_private_strong_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_directory(root)
            first = local_app.ensure_auth(root)
            second = local_app.ensure_auth(root)
            self.assertEqual(first, second)
            self.assertEqual(first["AUTOVUE_AUTH_USERNAME"], "autovue")
            self.assertGreaterEqual(len(first["AUTOVUE_AUTH_PASSWORD"]), 40)
            self.assertEqual((root / "auth.env").stat().st_mode & 0o777, 0o600)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)

    def test_read_auth_rejects_insecure_permissions_or_weak_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.env"
            local_app.private_write(path, "AUTOVUE_AUTH_USERNAME=autovue\nAUTOVUE_AUTH_PASSWORD=short\n")
            with self.assertRaisesRegex(local_app.ControlError, "at least 24"):
                local_app.read_auth(path)
            path.chmod(0o644)
            with self.assertRaisesRegex(local_app.ControlError, "private"):
                local_app.read_auth(path)

    def test_runtime_symlinks_cannot_read_or_overwrite_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "existing.txt"
            target.write_text("preserve-existing")
            alias = root / "auth.env"
            alias.symlink_to(target)
            with self.assertRaises(OSError):
                local_app.ensure_auth(root)
            with self.assertRaises(OSError):
                local_app.private_write(alias, "replacement")
            self.assertEqual(target.read_text(), "preserve-existing")

    def test_auth_file_is_data_and_never_shell_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.env"
            local_app.private_write(path, "AUTOVUE_AUTH_USERNAME=autovue\nAUTOVUE_AUTH_PASSWORD=$(touch /tmp/unwanted-command)\n")
            with self.assertRaises(local_app.ControlError):
                local_app.read_auth(path)

    def test_environment_forces_loopback_auth_and_separate_environments(self):
        with patch.dict(os.environ, {"AUTOVUE_REQUIRE_AUTH": "0", "AUTOVUE_CORS_ORIGINS": "*", "AUTOVUE_PUBLIC_MODE": "1", "AUTOVUE_PUBLIC_HOST": "review.ts.net", "PYTHONPATH": "/existing/modules"}):
            env = local_app.environment_for(Path("/test/repo"), Path("/test/jobs"), {
                "AUTOVUE_AUTH_USERNAME": "autovue", "AUTOVUE_AUTH_PASSWORD": "a" * 32,
            }, port=8181)
        self.assertEqual(env["AUTOVUE_REQUIRE_AUTH"], "1")
        self.assertEqual(env["AUTOVUE_CORS_ORIGINS"], "")
        self.assertEqual(env["AUTOVUE_LOCAL_HOSTS"], "127.0.0.1:8181,localhost:8181")
        self.assertEqual(env["AUTOVUE_PUBLIC_MODE"], "1")
        self.assertEqual(env["AUTOVUE_PUBLIC_HOST"], "review.ts.net")
        self.assertEqual(env["AUTOVUE_MAIN_PYTHON"], "/test/repo/.venv/bin/python")
        self.assertEqual(env["AUTOVUE_PADDLE_PYTHON"], "/test/repo/.venv_paddleocr/bin/python")
        self.assertEqual(env["PYTHONPATH"], "/test/repo/src:/test/repo:/existing/modules")

    def test_fresh_shell_adds_source_paths_for_uvicorn_and_pipeline(self):
        with patch.dict(os.environ, {}, clear=True):
            env = local_app.environment_for(Path("/test/repo"), Path("/test/jobs"), {
                "AUTOVUE_AUTH_USERNAME": "autovue", "AUTOVUE_AUTH_PASSWORD": "a" * 32,
            })
        self.assertEqual(env["PYTHONPATH"], "/test/repo/src:/test/repo")

    def test_occupied_port_is_refused_without_touching_other_process(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            with patch.object(local_app.os, "killpg") as kill:
                with self.assertRaisesRegex(local_app.ControlError, "occupied"):
                    local_app.check_port(occupied.getsockname()[1])
                kill.assert_not_called()

    def test_recent_closed_connection_allows_safe_server_restart(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    connection.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1), b"")
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(connection.recv(1), b"")
        # The accepted socket's local port remains in TIME_WAIT. A live
        # listener is still refused by the separate occupied-port test.
        local_app.check_port(port)

    def test_pid_reuse_and_foreign_session_are_not_owned(self):
        state = self.state()
        with patch.object(local_app, "process_identity", return_value=self.identity()):
            self.assertTrue(local_app.owned_process(state))
        reused = dict(self.identity(), start_ticks="9999")
        with patch.object(local_app, "process_identity", return_value=reused):
            self.assertFalse(local_app.owned_process(state))
        foreign = dict(self.identity(), session=1)
        state["process"] = foreign
        with patch.object(local_app, "process_identity", return_value=foreign):
            self.assertFalse(local_app.owned_process(state))

    def test_non_backend_process_is_never_owned(self):
        foreign = dict(self.identity(), command=["python3", "other-script.py"])
        state = self.state()
        state["process"] = foreign
        with patch.object(local_app, "process_identity", return_value=foreign):
            self.assertFalse(local_app.owned_process(state))

    def test_stop_does_not_signal_reused_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            with patch.object(local_app, "process_identity", return_value=dict(self.identity(), start_ticks="9999")), patch.object(local_app.os, "killpg") as kill:
                local_app.stop(root, force=True)
            kill.assert_not_called()

    def test_stop_refuses_active_gpu_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            local_app.ensure_auth(root)
            with patch.object(local_app, "process_identity", return_value=self.identity()), patch.object(local_app, "request_json", return_value={"jobs": [{"job_id": "running-job", "status": "OCR_PROCESSING"}]}), patch.object(local_app.os, "killpg") as kill:
                with self.assertRaisesRegex(local_app.ControlError, "HTTP 409"):
                    local_app.stop(root)
            kill.assert_not_called()

    def test_stop_refuses_unverifiable_api_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            local_app.ensure_auth(root)
            with patch.object(local_app, "process_identity", return_value=self.identity()), patch.object(local_app, "request_json", side_effect=OSError("offline")), patch.object(local_app.os, "killpg") as kill:
                with self.assertRaisesRegex(local_app.ControlError, "Cannot verify idle"):
                    local_app.stop(root)
            kill.assert_not_called()

    def test_normal_stop_signals_only_owned_group_and_keeps_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            local_app.ensure_auth(root)
            with patch.object(local_app, "owned_process", side_effect=[True, True, False]), patch.object(local_app, "request_json", return_value={"jobs": []}), patch.object(local_app.os, "killpg") as kill:
                local_app.stop(root)
            kill.assert_called_once_with(45678, signal.SIGTERM)
            self.assertTrue((root / "app.json").exists())
            self.assertTrue((root / "auth.env").exists())

    def test_start_refuses_auth_mode_change_for_already_running_app(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            with patch.dict(os.environ, {"AUTOVUE_PUBLIC_MODE": "1", "AUTOVUE_PUBLIC_HOST": "review.ts.net", "AUTOVUE_PUBLIC_ORIGIN": "https://review.ts.net"}), patch.object(local_app, "owned_process", return_value=True), patch.object(local_app.subprocess, "Popen") as begin:
                with self.assertRaisesRegex(local_app.ControlError, "different settings"):
                    local_app.start(root, port=8080, jobs_root=Path("/test/jobs"))
            begin.assert_not_called()

    def test_status_outputs_health_and_active_jobs_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_app.private_write(root / "app.json", json.dumps(self.state()))
            auth = local_app.ensure_auth(root)
            with patch.object(local_app, "owned_process", return_value=True), patch.object(local_app, "request_json", return_value={"jobs": [{"job_id": "finished", "status": "COMPLETED"}, {"job_id": "busy", "status": "RENDERING"}]}):
                result = local_app.status(root)
            self.assertTrue(result["running"])
            self.assertEqual(result["active_jobs"], ["busy"])
            self.assertNotIn(auth["AUTOVUE_AUTH_PASSWORD"], json.dumps(result))


if __name__ == "__main__":
    unittest.main()
