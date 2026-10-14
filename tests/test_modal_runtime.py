"""Exercise durable cloud dispatch without installing Modal or running inference."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from app.backend.services import jobs, runtime
from app.backend.worker.analysis import InvalidJobStateError, WorkerBusyError, _update_job
from deploy.runtime import ModalJobs, VolumeMiddleware


class FakeVolume:
    def __init__(self):
        self.events = []
        self.on_reload = None

    def commit(self):
        self.events.append("commit")

    def reload(self):
        self.events.append("reload")
        if self.on_reload:
            self.on_reload()


class FakeWorker:
    def __init__(self, volume):
        self.volume = volume
        self.calls = []
        self.on_spawn = None

    def spawn(self, job_id):
        self.calls.append(job_id)
        # The worker must be able to read a committed, QUEUED job on arrival.
        if jobs.load_job(job_id)["status"] != "QUEUED" or not self.volume.events:
            raise AssertionError("Worker spawned before queued state was committed")
        if self.on_spawn:
            self.on_spawn(job_id)
        return types.SimpleNamespace(object_id="fc-dispatch")


class FakeCall:
    def __init__(self, error=None, result=None):
        self.error = error
        self.result = result
        self.timeouts = []

    def get(self, *, timeout):
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return self.result


class ModalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root_patch = patch.object(jobs, "JOBS_ROOT", Path(self.temporary.name))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.volume = FakeVolume()
        self.commit_patch = patch.object(runtime, "commit_storage", self.volume.commit)
        self.commit_patch.start()
        self.addCleanup(self.commit_patch.stop)
        self.worker = FakeWorker(self.volume)
        self.call = FakeCall(error=TimeoutError())
        self.polled_ids = []
        self.cloud = ModalJobs(self.volume, self.worker, self.call_factory)

    def call_factory(self, call_id):
        self.polled_ids.append(call_id)
        return self.call

    def make_job(self, *, status="UPLOADED", receipt=None):
        manifest = jobs.create_job_manifest(original_filename="road.mp4", content_type="video/mp4")
        job_id = manifest["job_id"]
        jobs.job_input_path(job_id).write_bytes(b"representative input video bytes")
        manifest["status"] = status
        jobs.save_job_manifest(manifest)
        if receipt:
            self.receipt(job_id, receipt)
        return job_id

    def receipt(self, job_id, call_id, *, name="dispatch.json"):
        directory = jobs.job_input_path(job_id).parents[1]
        (directory / name).write_text(json.dumps({"call_id": call_id}))

    def manifest_bytes(self, job_id):
        return (jobs.job_input_path(job_id).parents[1] / "manifest.json").read_bytes()

    def modal_exceptions(self):
        package = types.ModuleType("modal")
        module = types.ModuleType("modal.exception")
        module.TimeoutError = type("TimeoutError", (Exception,), {})
        for name in ("ExecutionError", "RemoteError", "InternalFailure"):
            setattr(module, name, type(name, (Exception,), {}))
        for name in ("FunctionTimeoutError", "OutputExpiredError"):
            setattr(module, name, type(name, (module.TimeoutError,), {}))
        package.exception = module
        return package, module

    def test_dispatch_commits_queued_state_and_durable_call_receipt(self):
        job_id = self.make_job()
        result = self.cloud.dispatch(job_id)
        self.assertEqual((result["status"], result["progress"]), ("QUEUED", 5))
        self.assertEqual(jobs.load_job(job_id)["status"], "QUEUED")
        self.assertEqual(self.worker.calls, [job_id])
        self.assertEqual(self.volume.events, ["commit", "commit"])
        receipt = jobs.job_input_path(job_id).parents[1] / "dispatch.json"
        self.assertEqual(json.loads(receipt.read_text()), {"call_id": "fc-dispatch"})
        self.assertEqual(jobs.job_input_path(job_id).read_bytes(), b"representative input video bytes")

    def test_duplicate_dispatch_and_busy_worker_do_not_mutate_jobs(self):
        active = self.make_job(status="OCR_PROCESSING")
        pending = self.make_job()
        before = {job_id: self.manifest_bytes(job_id) for job_id in (active, pending)}
        with self.assertRaises(InvalidJobStateError):
            self.cloud.dispatch(active)
        with self.assertRaises(WorkerBusyError):
            self.cloud.dispatch(pending)
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(self.volume.events, [])
        for job_id, contents in before.items():
            self.assertEqual(self.manifest_bytes(job_id), contents)

    def test_missing_video_does_not_queue_job(self):
        job_id = self.make_job()
        jobs.job_input_path(job_id).unlink()
        before = self.manifest_bytes(job_id)
        with self.assertRaises(FileNotFoundError):
            self.cloud.dispatch(job_id)
        self.assertEqual(self.manifest_bytes(job_id), before)
        self.assertEqual(self.worker.calls, [])

    def test_ambiguous_spawn_error_does_not_overwrite_accepted_worker(self):
        job_id = self.make_job()

        def accepted_but_response_lost(accepted_job):
            _update_job(accepted_job, status="DETECTING_TRACKING", progress=10)
            raise ConnectionError("RPC response lost after worker accepted call")

        self.worker.on_spawn = accepted_but_response_lost
        with self.assertLogs("deploy.runtime", level="ERROR"):
            result = self.cloud.dispatch(job_id)
        self.assertEqual(result["status"], "QUEUED")
        self.assertEqual(jobs.load_job(job_id)["status"], "DETECTING_TRACKING")
        self.assertEqual(jobs.load_job(job_id)["progress"], 10)
        self.assertIsNone(jobs.load_job(job_id)["error"])

    def test_polling_running_call_keeps_manifest_exactly_unchanged(self):
        job_id = self.make_job(status="OCR_PROCESSING", receipt="fc-live")
        before = self.manifest_bytes(job_id)
        self.cloud.reconcile()
        self.assertEqual(self.manifest_bytes(job_id), before)
        self.assertEqual(self.polled_ids, ["fc-live"])
        self.assertEqual(self.call.timeouts, [0])
        self.assertEqual(self.volume.events, [])

    def test_worker_receipt_takes_precedence_over_dispatch_receipt(self):
        job_id = self.make_job(status="QUEUED", receipt="fc-dispatch")
        self.receipt(job_id, "fc-worker", name="worker_call.json")
        self.cloud.reconcile()
        self.assertEqual(self.polled_ids, ["fc-worker"])

    def test_completed_worker_state_is_reloaded_before_failure_decision(self):
        job_id = self.make_job(status="RENDERING", receipt="fc-finished")
        self.call = FakeCall(result="COMPLETED")

        def final_commit_visible():
            manifest = jobs.load_job(job_id)
            manifest.update(status="COMPLETED", progress=100, error=None)
            jobs.save_job_manifest(manifest)

        self.volume.on_reload = final_commit_visible
        self.cloud.reconcile()
        self.assertEqual(jobs.load_job(job_id)["status"], "COMPLETED")
        self.assertIsNone(jobs.load_job(job_id)["error"])
        self.assertEqual(self.volume.events, ["reload"])

    def test_ended_call_with_unfinished_manifest_becomes_failed(self):
        job_id = self.make_job(status="DETECTING_TRACKING", receipt="fc-ended")
        self.call = FakeCall(result=None)
        self.cloud.reconcile()
        manifest = jobs.load_job(job_id)
        self.assertEqual(manifest["status"], "FAILED")
        self.assertIn("without completing", manifest["error"])
        self.assertEqual(self.volume.events, ["reload", "commit"])

    def test_confirmed_modal_execution_failure_is_persisted(self):
        job_id = self.make_job(status="OCR_PROCESSING", receipt="fc-killed")
        package, exceptions = self.modal_exceptions()
        self.call = FakeCall(error=exceptions.FunctionTimeoutError("GPU timeout"))
        with patch.dict(sys.modules, {"modal": package, "modal.exception": exceptions}):
            self.cloud.reconcile()
        manifest = jobs.load_job(job_id)
        self.assertEqual(manifest["status"], "FAILED")
        self.assertIn("FunctionTimeoutError", manifest["error"])
        self.assertEqual(self.volume.events, ["reload", "commit"])

    def test_transient_poll_failure_never_reclaims_running_worker(self):
        job_id = self.make_job(status="OCR_PROCESSING", receipt="fc-running")
        before = self.manifest_bytes(job_id)
        package, exceptions = self.modal_exceptions()
        self.call = FakeCall(error=ConnectionError("temporary network error"))
        with patch.dict(sys.modules, {"modal": package, "modal.exception": exceptions}):
            with self.assertLogs("deploy.runtime", level="WARNING"):
                self.cloud.reconcile()
        self.assertEqual(self.manifest_bytes(job_id), before)
        self.assertEqual(self.volume.events, [])

    def test_modal_poll_timeout_keeps_running_job_without_warning(self):
        job_id = self.make_job(status="DETECTING_TRACKING", receipt="fc-still-running")
        before = self.manifest_bytes(job_id)
        package, exceptions = self.modal_exceptions()
        self.call = FakeCall(error=exceptions.TimeoutError("result is not ready"))
        with patch.dict(sys.modules, {"modal": package, "modal.exception": exceptions}):
            with self.assertNoLogs("deploy.runtime", level="WARNING"):
                self.cloud.reconcile()
        self.assertEqual(self.manifest_bytes(job_id), before)
        self.assertEqual(self.volume.events, [])

    def test_modal_internal_failure_reclaims_terminated_worker(self):
        job_id = self.make_job(status="OCR_PROCESSING", receipt="fc-internal-failure")
        package, exceptions = self.modal_exceptions()
        self.call = FakeCall(error=exceptions.InternalFailure("GPU container crashed"))
        with patch.dict(sys.modules, {"modal": package, "modal.exception": exceptions}):
            self.cloud.reconcile()
        self.assertEqual(jobs.load_job(job_id)["status"], "FAILED")
        self.assertIn("InternalFailure", jobs.load_job(job_id)["error"])
        self.assertEqual(self.volume.events, ["reload", "commit"])

    def test_remote_python_startup_failure_is_terminal(self):
        job_id = self.make_job(status="QUEUED", receipt="fc-startup-error")
        package, exceptions = self.modal_exceptions()
        error = FileNotFoundError("worker model asset is missing")
        # Modal adds remote traceback metadata to re-raised Python exceptions.
        error.__line_cache__ = {("remote_worker.py", 1): "load_model()"}
        self.call = FakeCall(error=error)
        with patch.dict(sys.modules, {"modal": package, "modal.exception": exceptions}):
            self.cloud.reconcile()
        self.assertEqual(jobs.load_job(job_id)["status"], "FAILED")
        self.assertIn("FileNotFoundError", jobs.load_job(job_id)["error"])
        self.assertEqual(self.volume.events, ["reload", "commit"])

    def test_failure_recorded_by_worker_survives_reconciliation(self):
        job_id = self.make_job(status="OCR_PROCESSING", receipt="fc-failed")
        self.call = FakeCall(result="FAILED")

        def worker_failure_visible():
            manifest = jobs.load_job(job_id)
            manifest.update(status="FAILED", progress=45, error="OCR stage failed: original detail")
            jobs.save_job_manifest(manifest)

        self.volume.on_reload = worker_failure_visible
        self.cloud.reconcile()
        manifest = jobs.load_job(job_id)
        self.assertEqual(manifest["status"], "FAILED")
        self.assertEqual(manifest["progress"], 45)
        self.assertEqual(manifest["error"], "OCR stage failed: original detail")
        self.assertEqual(self.volume.events, ["reload"])

    def test_missing_dispatch_receipt_gets_grace_then_persisted_failure(self):
        job_id = self.make_job(status="QUEUED")
        before = self.manifest_bytes(job_id)
        self.cloud.reconcile()
        self.assertEqual(self.manifest_bytes(job_id), before)
        manifest = jobs.load_job(job_id)
        manifest["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=4300)).isoformat()
        path = jobs.job_input_path(job_id).parents[1] / "manifest.json"
        path.write_text(json.dumps(manifest))
        self.cloud.reconcile()
        self.assertEqual(jobs.load_job(job_id)["status"], "FAILED")
        self.assertIn("dispatch was interrupted", jobs.load_job(job_id)["error"])
        self.assertEqual(self.volume.events, ["commit"])


class VolumeMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.events = []
        self.volume = FakeVolume()
        self.cloud = types.SimpleNamespace(volume=self.volume, reconcile=lambda: self.events.append("reconcile"))
        self.messages = []

    async def receive(self):
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(self, message):
        self.events.append(message["type"])
        self.messages.append(message)

    async def response(self, scope, receive, send):
        self.events.append("mutation")
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"saved"})

    async def test_mutation_is_committed_before_success_response_starts(self):
        def commit():
            self.events.append("commit")

        self.volume.commit = commit
        middleware = VolumeMiddleware(self.response, jobs=self.cloud)
        await middleware({"type": "http", "path": "/api/jobs", "method": "POST"}, self.receive, self.send)
        self.assertEqual(self.events, ["reconcile", "mutation", "commit", "http.response.start", "http.response.body"])
        self.assertEqual(self.messages[0]["status"], 201)
        self.assertEqual(self.volume.events, ["reload"])

    async def test_commit_failure_returns_503_before_any_success_response(self):
        def commit():
            self.events.append("commit")
            raise OSError("persistent storage unavailable")

        self.volume.commit = commit
        middleware = VolumeMiddleware(self.response, jobs=self.cloud)
        with self.assertLogs("deploy.runtime", level="ERROR"):
            await middleware({"type": "http", "path": "/api/jobs", "method": "POST"}, self.receive, self.send)
        self.assertEqual([message["status"] for message in self.messages if message["type"] == "http.response.start"], [503])
        self.assertIn(b"durably saved", self.messages[-1]["body"])

    async def test_reload_failure_rejects_request_without_calling_application(self):
        def reload():
            raise OSError("volume cannot reload")

        self.volume.reload = reload
        middleware = VolumeMiddleware(self.response, jobs=self.cloud)
        with self.assertLogs("deploy.runtime", level="ERROR"):
            await middleware({"type": "http", "path": "/api/jobs", "method": "GET"}, self.receive, self.send)
        self.assertNotIn("mutation", self.events)
        self.assertEqual(self.messages[0]["status"], 503)

    async def test_streamed_read_has_no_commit_and_reload_finishes_before_open(self):
        opened = False

        async def stream(scope, receive, send):
            nonlocal opened
            self.assertEqual(self.volume.events, ["reload"])
            self.assertEqual(self.events, ["reconcile"])
            opened = True
            await send({"type": "http.response.start", "status": 206, "headers": []})
            await send({"type": "http.response.body", "body": b"first", "more_body": True})
            await asyncio.sleep(0)
            self.assertEqual(self.volume.events, ["reload"])
            await send({"type": "http.response.body", "body": b"last", "more_body": False})

        middleware = VolumeMiddleware(stream, jobs=self.cloud)
        await middleware({"type": "http", "path": "/api/jobs/one/video/original", "method": "GET"}, self.receive, self.send)
        self.assertTrue(opened)
        self.assertEqual([m.get("body") for m in self.messages[1:]], [b"first", b"last"])
        self.assertEqual(self.volume.events, ["reload"])

    async def test_frontend_requests_bypass_job_volume(self):
        middleware = VolumeMiddleware(self.response, jobs=self.cloud)
        await middleware({"type": "http", "path": "/assets/app.js", "method": "GET"}, self.receive, self.send)
        self.assertEqual(self.volume.events, [])
        self.assertNotIn("reconcile", self.events)


if __name__ == "__main__":
    unittest.main()
