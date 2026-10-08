from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import os
from pathlib import Path
import subprocess
import threading
from typing import Any

from app.backend.services.jobs import (
    job_input_path,
    load_job,
    save_job_manifest,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

MAIN_PYTHON = (
    PROJECT_ROOT
    / ".venv"
    / "bin"
    / "python"
)

PADDLE_PYTHON = (
    PROJECT_ROOT
    / ".venv_paddleocr"
    / "bin"
    / "python"
)


ACTIVE_STATUSES = {
    "QUEUED",
    "DETECTING_TRACKING",
    "OCR_PROCESSING",
    "TEMPORAL_CONSENSUS",
    "RENDERING",
}


_state_lock = threading.Lock()
_active_job_id: str | None = None


class WorkerBusyError(RuntimeError):
    pass


class InvalidJobStateError(RuntimeError):
    pass


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def get_active_job_id() -> str | None:

    with _state_lock:
        return _active_job_id


def _job_dir(
    job_id: str,
) -> Path:

    return (
        job_input_path(job_id)
        .parents[1]
        .resolve()
    )


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:

    manifest = load_job(
        job_id
    )

    if status is not None:
        manifest["status"] = (
            status
        )

    if progress is not None:
        manifest["progress"] = (
            max(
                0,
                min(
                    100,
                    int(progress),
                ),
            )
        )

    if message is not None:
        manifest["message"] = (
            message
        )

    manifest["error"] = (
        error
    )

    if extra:
        manifest.update(
            extra
        )

    save_job_manifest(
        manifest
    )

    return manifest


def _tail_log(
    path: Path,
    *,
    lines: int = 20,
) -> str:

    if not path.exists():
        return ""

    try:
        content = (
            path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            .splitlines()
        )

    except OSError:
        return ""

    return "\n".join(
        content[-lines:]
    )


def _run_command(
    *,
    job_id: str,
    stage_name: str,
    command: list[str],
) -> None:

    job_dir = _job_dir(
        job_id
    )

    log_dir = (
        job_dir
        / "logs"
    )

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        log_dir
        / "analysis.log"
    )

    env = os.environ.copy()

    src_path = str(
        PROJECT_ROOT
        / "src"
    )

    existing_pythonpath = (
        env.get(
            "PYTHONPATH",
            "",
        )
    )

    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else (
            src_path
            + os.pathsep
            + existing_pythonpath
        )
    )

    env["PYTHONUNBUFFERED"] = (
        "1"
    )

    env.setdefault(
        "YOLO_CONFIG_DIR",
        str(
            Path.home()
            / ".ultralytics"
        ),
    )

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as log:

        log.write(
            "\n"
            + "=" * 72
            + "\n"
        )

        log.write(
            f"STAGE: {stage_name}\n"
        )

        log.write(
            "COMMAND: "
            + " ".join(command)
            + "\n"
        )

        log.write(
            "=" * 72
            + "\n"
        )

        log.flush()

        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )

    if completed.returncode != 0:

        tail = _tail_log(
            log_path
        )

        raise RuntimeError(
            f"{stage_name} failed "
            f"with exit code "
            f"{completed.returncode}."
            + (
                "\n\n"
                + tail
                if tail
                else ""
            )
        )


def _run_pipeline(
    job_id: str,
) -> None:

    job_dir = _job_dir(
        job_id
    )

    input_video = (
        job_input_path(
            job_id
        )
        .resolve()
    )

    try:

        if not input_video.exists():
            raise FileNotFoundError(
                input_video
            )

        if not MAIN_PYTHON.exists():
            raise FileNotFoundError(
                MAIN_PYTHON
            )

        if not PADDLE_PYTHON.exists():
            raise FileNotFoundError(
                PADDLE_PYTHON
            )

        # -------------------------------------------------
        # 1. TRACKING
        # -------------------------------------------------

        _update_job(
            job_id,
            status="DETECTING_TRACKING",
            progress=10,
            message=(
                "Detecting vehicles, tracking "
                "them and selecting plate crops."
            ),
            error=None,
            extra={
                "started_at":
                    _utc_now(),
            },
        )

        _run_command(
            job_id=job_id,
            stage_name=(
                "Vehicle detection, tracking "
                "and plate crop selection"
            ),
            command=[
                str(MAIN_PYTHON),
                "-m",
                "autovue.pipeline.tracking",
                "--input",
                str(input_video),
                "--job-dir",
                str(job_dir),
            ],
        )

        # -------------------------------------------------
        # 2. CONSERVATIVE REASSOCIATION
        # -------------------------------------------------

        _update_job(
            job_id,
            status="DETECTING_TRACKING",
            progress=35,
            message=(
                "Applying conservative "
                "track reassociation."
            ),
        )

        _run_command(
            job_id=job_id,
            stage_name=(
                "Conservative track "
                "reassociation"
            ),
            command=[
                str(MAIN_PYTHON),
                "-m",
                "autovue.pipeline.reassociation",
                "--job-dir",
                str(job_dir),
            ],
        )

        # -------------------------------------------------
        # 3. PADDLE OCR
        # -------------------------------------------------

        _update_job(
            job_id,
            status="OCR_PROCESSING",
            progress=45,
            message=(
                "Running PaddleOCR, Indian "
                "plate parsing and rescue logic."
            ),
        )

        _run_command(
            job_id=job_id,
            stage_name=(
                "PaddleOCR and Indian "
                "plate parsing"
            ),
            command=[
                str(PADDLE_PYTHON),
                "-m",
                "autovue.pipeline.ocr",
                "--job-dir",
                str(job_dir),
            ],
        )

        # -------------------------------------------------
        # 4. TEMPORAL CONSENSUS
        # -------------------------------------------------

        _update_job(
            job_id,
            status="TEMPORAL_CONSENSUS",
            progress=75,
            message=(
                "Combining multi-frame OCR "
                "evidence across track clusters."
            ),
        )

        _run_command(
            job_id=job_id,
            stage_name=(
                "Temporal consensus and "
                "fragment corroboration"
            ),
            command=[
                str(MAIN_PYTHON),
                "-m",
                "autovue.pipeline.consensus",
                "--job-dir",
                str(job_dir),
            ],
        )

        # -------------------------------------------------
        # 5. CANONICAL RESULT + VIDEO
        # -------------------------------------------------

        _update_job(
            job_id,
            status="RENDERING",
            progress=88,
            message=(
                "Building canonical results "
                "and rendering analyzed video."
            ),
        )

        _run_command(
            job_id=job_id,
            stage_name=(
                "Canonical result and "
                "analyzed video"
            ),
            command=[
                str(MAIN_PYTHON),
                "-m",
                "autovue.pipeline.finalize",
                "--job-dir",
                str(job_dir),
            ],
        )

        canonical = (
            job_dir
            / "canonical_result.json"
        )

        analyzed = (
            job_dir
            / "video"
            / "analyzed.mp4"
        )

        if not canonical.exists():
            raise RuntimeError(
                "Pipeline finished but "
                "canonical_result.json "
                "is missing."
            )

        if not analyzed.exists():
            raise RuntimeError(
                "Pipeline finished but "
                "analyzed.mp4 is missing."
            )

        _update_job(
            job_id,
            status="COMPLETED",
            progress=100,
            message=(
                "AutoVue analysis completed "
                "successfully."
            ),
            error=None,
            extra={
                "completed_at":
                    _utc_now(),
            },
        )

    except Exception as exc:

        try:
            current = load_job(
                job_id
            )

            progress = int(
                current.get(
                    "progress",
                    0,
                )
            )

        except Exception:
            progress = 0

        _update_job(
            job_id,
            status="FAILED",
            progress=progress,
            message=(
                "AutoVue analysis failed."
            ),
            error=str(exc),
            extra={
                "completed_at":
                    _utc_now(),
            },
        )

    finally:

        global _active_job_id

        with _state_lock:

            if (
                _active_job_id
                == job_id
            ):
                _active_job_id = (
                    None
                )


def start_analysis_job(
    job_id: str,
) -> dict[str, Any]:

    manifest = load_job(
        job_id
    )

    status = str(
        manifest.get(
            "status",
            "",
        )
    )

    if status != "UPLOADED":

        raise InvalidJobStateError(
            "Only an UPLOADED job can "
            "be started. "
            f"Current status: {status}"
        )

    input_video = job_input_path(
        job_id
    )

    if not input_video.exists():
        raise FileNotFoundError(
            input_video
        )

    global _active_job_id

    with _state_lock:

        if _active_job_id is not None:

            raise WorkerBusyError(
                "Another AutoVue analysis "
                "job is currently running: "
                f"{_active_job_id}"
            )

        _active_job_id = (
            job_id
        )

    try:

        queued = _update_job(
            job_id,
            status="QUEUED",
            progress=5,
            message=(
                "Job accepted. Waiting for "
                "the AutoVue analysis worker."
            ),
            error=None,
        )

        thread = threading.Thread(
            target=_run_pipeline,
            args=(job_id,),
            name=(
                f"autovue-job-"
                f"{job_id[:8]}"
            ),
            daemon=True,
        )

        thread.start()

        return queued

    except Exception:

        with _state_lock:

            if (
                _active_job_id
                == job_id
            ):
                _active_job_id = (
                    None
                )

        raise
