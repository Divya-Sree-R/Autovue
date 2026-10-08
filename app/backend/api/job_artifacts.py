from __future__ import annotations

import json
from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import (
    FileResponse,
)

from app.backend.services.jobs import (
    job_input_path,
    load_job,
)


router = APIRouter(
    prefix="/api/jobs",
    tags=["Analysis Job Artifacts"],
)


def _job_dir(
    job_id: str,
) -> Path:
    """
    Validate that the job exists, then return its
    product workspace directory.
    """

    try:
        load_job(
            job_id
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    return (
        job_input_path(job_id)
        .parents[1]
        .resolve()
    )


def _require_file(
    path: Path,
    label: str,
) -> Path:

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"{label} is not available."
            ),
        )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"{label} is not available."
            ),
        )

    return path


def _canonical_result(
    job_id: str,
) -> dict:

    job_dir = _job_dir(
        job_id
    )

    result_path = _require_file(
        job_dir
        / "canonical_result.json",
        "Canonical AutoVue result",
    )

    try:
        return json.loads(
            result_path.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Canonical AutoVue result "
                "could not be read."
            ),
        ) from exc


@router.get(
    "/{job_id}/results"
)
def job_results(
    job_id: str,
):
    """
    Return the complete canonical result produced
    by the AutoVue product pipeline.
    """

    return _canonical_result(
        job_id
    )


@router.get(
    "/{job_id}/summary"
)
def job_summary(
    job_id: str,
):

    result = _canonical_result(
        job_id
    )

    return {
        "schema_version":
            result["schema_version"],

        "source":
            result["source"],

        "ground_truth_used":
            result["ground_truth_used"],

        "summary":
            result["summary"],
    }


@router.get(
    "/{job_id}/clusters/{cluster_id}"
)
def job_cluster(
    job_id: str,
    cluster_id: int,
):

    result = _canonical_result(
        job_id
    )

    for cluster in result.get(
        "clusters",
        [],
    ):
        if (
            cluster.get(
                "cluster_id"
            )
            == cluster_id
        ):
            return cluster

    raise HTTPException(
        status_code=404,
        detail=(
            f"Cluster {cluster_id} "
            "was not found."
        ),
    )


@router.get(
    "/{job_id}/videos"
)
def job_videos(
    job_id: str,
):
    """
    Return stable API URLs for the job's videos.
    """

    _job_dir(
        job_id
    )

    base = (
        f"/api/jobs/{job_id}/video"
    )

    return {
        "original":
            f"{base}/original",

        "tracking":
            f"{base}/tracking",

        "analyzed":
            f"{base}/analyzed",
    }


@router.get(
    "/{job_id}/video/original"
)
def job_original_video(
    job_id: str,
):

    job_dir = _job_dir(
        job_id
    )

    path = _require_file(
        job_dir
        / "input"
        / "original.mp4",
        "Original job video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get(
    "/{job_id}/video/tracking"
)
def job_tracking_video(
    job_id: str,
):

    job_dir = _job_dir(
        job_id
    )

    path = _require_file(
        job_dir
        / "video"
        / "tracking.mp4",
        "Tracking video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get(
    "/{job_id}/video/analyzed"
)
def job_analyzed_video(
    job_id: str,
):

    job_dir = _job_dir(
        job_id
    )

    path = _require_file(
        job_dir
        / "video"
        / "analyzed.mp4",
        "Analyzed AutoVue video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get(
    "/{job_id}/crops/{filename}"
)
def job_plate_crop(
    job_id: str,
    filename: str,
):

    # Prevent:
    #
    # ../../secret
    #
    # and similar path traversal.
    if (
        Path(filename).name
        != filename
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid crop filename."
            ),
        )

    job_dir = _job_dir(
        job_id
    )

    path = _require_file(
        job_dir
        / "crops"
        / filename,
        "Plate crop",
    )

    return FileResponse(
        path,
        media_type="image/jpeg",
    )
