from __future__ import annotations

from pathlib import Path

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
    job_input_path,
    list_jobs,
    load_job,
    save_job_manifest,
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
