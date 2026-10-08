from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from autovue.result_loader import (
    load_frozen_m25_result,
)

from app.backend.config import (
    ANALYZED_VIDEO,
    CROP_DIR,
    FROZEN_OUTPUT_ROOT,
    ORIGINAL_VIDEO,
    TRACKING_VIDEO,
)


router = APIRouter(
    prefix="/api/reference",
    tags=["Reference Evaluation"],
)


@lru_cache(maxsize=1)
def _reference_result() -> dict:
    """
    Load the frozen M25 AutoVue result.

    This does not run inference and does not modify the
    frozen research pipeline.
    """
    result = load_frozen_m25_result(
        FROZEN_OUTPUT_ROOT
    )

    return result.to_dict()


def _require_file(
    path: Path,
    label: str,
) -> Path:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{label} is not available.",
        )

    return path


@router.get("/summary")
def reference_summary():
    result = _reference_result()

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


@router.get("/results")
def reference_results():
    """
    Return the complete canonical AutoVue reference result.
    """
    return _reference_result()


@router.get("/clusters/{cluster_id}")
def reference_cluster(
    cluster_id: int,
):
    result = _reference_result()

    for cluster in result["clusters"]:
        if (
            cluster["cluster_id"]
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


@router.get("/videos")
def reference_videos():
    """
    URLs consumed later by the React synchronized
    video player.
    """
    return {
        "original":
            "/api/reference/video/original",

        "tracking":
            "/api/reference/video/tracking",

        "analyzed":
            "/api/reference/video/analyzed",
    }


@router.get("/video/original")
def original_video():
    path = _require_file(
        ORIGINAL_VIDEO,
        "Original M25 video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get("/video/tracking")
def tracking_video():
    path = _require_file(
        TRACKING_VIDEO,
        "M25 tracking video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get("/video/analyzed")
def analyzed_video():
    path = _require_file(
        ANALYZED_VIDEO,
        "AutoVue analyzed video",
    )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@router.get("/crops/{filename}")
def plate_crop(
    filename: str,
):
    # Prevent path traversal such as ../../file
    if Path(filename).name != filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid crop filename.",
        )

    path = CROP_DIR / filename

    path = _require_file(
        path,
        "Plate crop",
    )

    return FileResponse(
        path,
        media_type="image/jpeg",
    )
