from __future__ import annotations

from pathlib import Path

import cv2

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.backend.services.jobs import (
    ALLOWED_VIDEO_SUFFIXES,
    MAX_UPLOAD_BYTES,
    create_job_manifest,
    delete_job_files,
    job_input_path,
    list_jobs,
    load_job,
    save_job_manifest,
)

from app.backend.worker.analysis import (
    InvalidJobStateError,
    WorkerBusyError,
    get_active_job_id,
    start_analysis_job,
)


router = APIRouter(
    prefix="/api/jobs",
    tags=["Analysis Jobs"],
)


@router.get("")
def get_jobs():
    return {
        "jobs": list_jobs(),
    }


@router.get("/{job_id}")
def get_job(
    job_id: str,
):
    try:
        return load_job(job_id)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )


ACTIVE_JOB_STATUSES = {
    "QUEUED",
    "DETECTING_TRACKING",
    "OCR_PROCESSING",
    "TEMPORAL_CONSENSUS",
    "RENDERING",
}


@router.delete(
    "/{job_id}"
)
def delete_job(
    job_id: str,
):
    try:
        manifest = load_job(
            job_id
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )


    if (
        manifest.get("status")
        in ACTIVE_JOB_STATUSES
        or get_active_job_id()
        == job_id
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "A running analysis cannot "
                "be deleted. Wait for it to "
                "finish or fail first."
            ),
        )


    try:
        delete_job_files(
            job_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )


    return {
        "job_id":
            job_id,

        "deleted":
            True,
    }


@router.post(
    "/{job_id}/run",
    status_code=202,
)
def run_job(
    job_id: str,
):
    try:
        return start_analysis_job(
            job_id
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    except InvalidJobStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except WorkerBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


@router.post(
    "",
    status_code=201,
)
async def create_job(
    file: UploadFile = File(...),
):

    filename = (
        file.filename
        or "video.mp4"
    )

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        await file.close()

        raise HTTPException(
            status_code=415,
            detail=(
                "Only MP4 videos "
                "are currently supported."
            ),
        )

    manifest = create_job_manifest(
        original_filename=filename,
        content_type=file.content_type,
    )

    output_path = job_input_path(
        manifest["job_id"]
    )

    size_bytes = 0

    try:
        with output_path.open(
            "wb"
        ) as destination:

            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                size_bytes += len(chunk)

                if (
                    size_bytes
                    > MAX_UPLOAD_BYTES
                ):
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Video exceeds the "
                            "500 MB upload limit."
                        ),
                    )

                destination.write(
                    chunk
                )

        if size_bytes == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Uploaded video is empty."
                ),
            )


        capture = cv2.VideoCapture(
            str(output_path)
        )

        try:
            if not capture.isOpened():
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Uploaded MP4 could not "
                        "be opened as a video."
                    ),
                )


            readable, frame = (
                capture.read()
            )

            if (
                not readable
                or frame is None
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Uploaded MP4 contains "
                        "no readable video frames."
                    ),
                )

        finally:
            capture.release()


    except Exception:
        try:
            delete_job_files(
                manifest["job_id"]
            )

        except Exception:
            output_path.unlink(
                missing_ok=True
            )

        raise

    finally:
        await file.close()


    manifest["size_bytes"] = (
        size_bytes
    )

    save_job_manifest(
        manifest
    )

    return manifest
