from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import json
import shutil


from app.backend.config import PROJECT_ROOT


JOBS_ROOT = (
    PROJECT_ROOT
    / "app_data"
    / "jobs"
)

MAX_UPLOAD_BYTES = (
    500 * 1024 * 1024
)

ALLOWED_VIDEO_SUFFIXES = {
    ".mp4",
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
    )


def _manifest_path(
    job_id: str,
) -> Path:
    return (
        JOBS_ROOT
        / job_id
        / "manifest.json"
    )


def _write_manifest(
    path: Path,
    data: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        ".json.tmp"
    )

    temporary.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


def create_job_manifest(
    *,
    original_filename: str,
    content_type: str | None,
) -> dict[str, Any]:

    job_id = str(uuid4())

    now = _utc_now()

    job_dir = JOBS_ROOT / job_id

    (
        job_dir
        / "input"
    ).mkdir(
        parents=True,
        exist_ok=False,
    )

    (
        job_dir
        / "crops"
    ).mkdir()

    (
        job_dir
        / "metadata"
    ).mkdir()

    (
        job_dir
        / "video"
    ).mkdir()

    manifest = {
        "job_id": job_id,

        "status": "UPLOADED",

        "progress": 0,

        "message":
            "Video uploaded. "
            "Analysis has not started.",

        "original_filename":
            original_filename,

        "stored_filename":
            "original.mp4",

        "content_type":
            content_type,

        "size_bytes":
            0,

        "created_at":
            now,

        "updated_at":
            now,

        "error":
            None,
    }

    _write_manifest(
        _manifest_path(job_id),
        manifest,
    )

    return manifest


def save_job_manifest(
    manifest: dict[str, Any],
) -> None:

    manifest["updated_at"] = (
        _utc_now()
    )

    _write_manifest(
        _manifest_path(
            manifest["job_id"]
        ),
        manifest,
    )


def load_job(
    job_id: str,
) -> dict[str, Any]:

    path = _manifest_path(job_id)

    if not path.exists():
        raise FileNotFoundError(
            job_id
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def list_jobs() -> list[dict[str, Any]]:

    if not JOBS_ROOT.exists():
        return []

    jobs: list[dict[str, Any]] = []

    for directory in JOBS_ROOT.iterdir():

        if not directory.is_dir():
            continue

        manifest_path = (
            directory
            / "manifest.json"
        )

        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            continue

        jobs.append(manifest)

    jobs.sort(
        key=lambda item:
            item.get(
                "created_at",
                "",
            ),
        reverse=True,
    )

    return jobs


def job_input_path(
    job_id: str,
) -> Path:

    return (
        JOBS_ROOT
        / job_id
        / "input"
        / "original.mp4"
    )



def delete_job_files(
    job_id: str,
) -> None:
    """
    Permanently delete one AutoVue job workspace.

    load_job() first ensures that only a real manifest-backed
    product job can be deleted. The frozen m25_reference
    directory has no product manifest and therefore cannot
    be deleted through this function.
    """

    load_job(
        job_id
    )

    jobs_root = (
        JOBS_ROOT
        .resolve()
    )

    job_dir = (
        JOBS_ROOT
        / job_id
    ).resolve()

    # Safety: deletion must remain directly inside JOBS_ROOT.
    if job_dir.parent != jobs_root:
        raise ValueError(
            "Invalid job workspace."
        )

    if not job_dir.exists():
        raise FileNotFoundError(
            job_id
        )

    shutil.rmtree(
        job_dir
    )
