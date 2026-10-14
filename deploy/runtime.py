"""Modal dispatch and filesystem synchronization, without changing API schemas.

The web container handles one request at a time, including the entire file
response. This prevents Volume.reload while a video/upload has an open handle.
Only the GPU worker writes a running job's manifest. Web writes dispatch.json;
worker writes worker_call.json, so their commits never overwrite the same file.
"""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.backend.services import runtime
from app.backend.services.jobs import job_input_path, list_jobs, load_job
from app.backend.worker.analysis import (
    ACTIVE_STATUSES, InvalidJobStateError, WorkerBusyError, _update_job,
)

logger = logging.getLogger(__name__)


class ModalJobs:
    def __init__(self, volume, worker, call_factory):
        self.volume = volume
        self.worker = worker
        self.call_factory = call_factory

    def dispatch(self, job_id: str) -> dict:
        manifest = load_job(job_id)
        if manifest['status'] != 'UPLOADED':
            raise InvalidJobStateError(
                f"Only an UPLOADED job can be started. Current status: {manifest['status']}"
            )
        if any(job['status'] in ACTIVE_STATUSES for job in list_jobs()):
            raise WorkerBusyError('Another AutoVue analysis job is currently running.')
        if not job_input_path(job_id).is_file():
            raise FileNotFoundError(job_id)
        # _update_job commits the completed upload before a remote worker reads it.
        queued = _update_job(job_id, status='QUEUED', progress=5,
                             message='Job accepted. Waiting for the AutoVue analysis worker.')
        try:
            call = self.worker.spawn(job_id)
            receipt = job_input_path(job_id).parents[1] / 'dispatch.json'
            receipt.write_text(json.dumps({'call_id': call.object_id}), encoding='utf-8')
            self.volume.commit()
        except Exception:
            # An RPC failure can occur after acceptance. Do not overwrite a
            # manifest a worker might already own; reconciliation resolves it.
            logger.exception('Modal dispatch did not return a durable receipt for %s', job_id)
        return queued

    def reconcile(self) -> None:
        for job in list_jobs():
            if job['status'] not in ACTIVE_STATUSES:
                continue
            job_id = job['job_id']
            directory = job_input_path(job_id).parents[1]
            receipt = next((directory / name for name in ('worker_call.json', 'dispatch.json')
                            if (directory / name).is_file()), None)
            if receipt is None:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(job['updated_at'])).total_seconds()
                # A web process may die between committing QUEUED and spawning.
                # Worker creates its own receipt before starting any stage.
                if age > 4200:
                    _update_job(job_id, status='FAILED', message='AutoVue analysis failed.',
                                error='Worker dispatch was interrupted before a receipt was saved.')
                continue
            try:
                call_id = json.loads(receipt.read_text())['call_id']
                self.call_factory(call_id).get(timeout=0)
            except TimeoutError:
                continue  # Still queued/running; never write its manifest.
            except Exception as exc:
                # Only confirmed execution failures may reclaim worker ownership.
                # Transient network/auth errors must not turn running jobs FAILED.
                from modal import exception as errors
                terminal_errors = tuple(getattr(errors, name) for name in (
                    'ExecutionError', 'FunctionTimeoutError', 'OutputExpiredError',
                    'RemoteError', 'InternalFailure') if hasattr(errors, name))
                if not isinstance(exc, terminal_errors) and not hasattr(exc, '__line_cache__'):
                    if isinstance(exc, getattr(errors, 'TimeoutError', TimeoutError)):
                        continue  # SDK polling timeout (distinct from function timeout).
                    logger.warning('Unable to poll worker %s: %s', job_id, type(exc).__name__)
                    continue
                failure = f'Modal worker terminated: {type(exc).__name__}.'
            else:
                failure = 'Modal worker ended without completing its job.'
            # The call has ended. Reload to see the worker's last committed state.
            self.volume.reload()
            if load_job(job_id)['status'] in ACTIVE_STATUSES:
                _update_job(job_id, status='FAILED', message='AutoVue analysis failed.', error=failure)


class VolumeMiddleware:
    def __init__(self, app, *, jobs: ModalJobs):
        self.app = app
        self.jobs = jobs

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path', '').startswith('/api/'):
            return await self.app(scope, receive, send)
        try:
            await run_in_threadpool(self.jobs.volume.reload)
            await run_in_threadpool(self.jobs.reconcile)
        except Exception:
            logger.exception('Persistent storage is unavailable')
            return await JSONResponse({'detail': 'Persistent job storage is temporarily unavailable.'},
                                      status_code=503)(scope, receive, send)
        mutation = scope['method'] in {'POST', 'DELETE', 'PUT', 'PATCH'}

        async def durable_send(message):
            if mutation and message['type'] == 'http.response.start':
                try:
                    await run_in_threadpool(self.jobs.volume.commit)
                except Exception as exc:
                    raise StorageCommitError from exc
            await send(message)

        try:
            await self.app(scope, receive, durable_send)
        except StorageCommitError:
            logger.exception('Could not persist the mutation')
            await JSONResponse({'detail': 'The operation could not be durably saved.'},
                               status_code=503)(scope, receive, send)


class StorageCommitError(RuntimeError):
    pass


def attach(application, *, volume, worker, call_factory):
    runtime.commit_storage = volume.commit
    jobs = ModalJobs(volume, worker, call_factory)
    runtime.dispatch_analysis = jobs.dispatch
    # Authentication must run before storage work. Insert as innermost middleware.
    from starlette.middleware import Middleware
    application.user_middleware.append(Middleware(VolumeMiddleware, jobs=jobs))
    return application
