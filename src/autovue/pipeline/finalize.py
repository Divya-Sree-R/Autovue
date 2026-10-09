from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from autovue.presentation_renderer import (
    render_presentation_video,
)
from autovue.result_loader import (
    load_frozen_m25_result,
)


def _build_compatibility_view(
    *,
    job_dir: Path,
    temp_root: Path,
) -> Path:
    """
    Create a temporary filesystem layout matching the
    already-validated frozen M25 result loader.

    No research artifacts are modified.
    """

    metadata = (
        job_dir
        / "metadata"
    )

    tracking_dir = (
        temp_root
        / "M25B_tracking"
    )

    tracking_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    mappings = {
        metadata / "track_summary.csv":
            tracking_dir
            / "track_summary.csv",

        metadata / "frame_predictions.csv":
            temp_root
            / "M25D_frame_predictions.csv",

        metadata / "candidate_options.csv":
            temp_root
            / "M25E_candidate_options.csv",

        metadata / "fragment_evidence.csv":
            temp_root
            / "M25E_fragment_evidence.csv",

        metadata / "cluster_consensus.csv":
            temp_root
            / "M25E_cluster_consensus.csv",
    }

    for source, destination in mappings.items():

        if not source.exists():
            raise FileNotFoundError(
                source
            )

        shutil.copy2(
            source,
            destination,
        )

    return temp_root


def build_canonical_result(
    *,
    job_dir: Path,
) -> Path:
    """
    Build canonical_result.json for one AutoVue product job.

    Reuses the validated M26A canonical loader.
    """

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    output_path = (
        job_dir
        / "canonical_result.json"
    )

    with tempfile.TemporaryDirectory(
        prefix="autovue_result_"
    ) as temp_name:

        temp_root = Path(
            temp_name
        )

        compatibility_root = (
            _build_compatibility_view(
                job_dir=job_dir,
                temp_root=temp_root,
            )
        )

        result = (
            load_frozen_m25_result(
                compatibility_root
            )
        )

    # The loader is shared with the frozen reference case.
    # For an uploaded product job, replace only the source
    # descriptor. Scientific result contents remain unchanged.
    result.source = (
        f"autovue_product_job:"
        f"{job_dir.name}"
    )

    output_path.write_text(
        json.dumps(
            result.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Canonical result:",
        output_path,
    )

    return output_path


def render_job_presentation(
    *,
    job_dir: Path,
) -> Path:
    """
    Create the clean dashboard/presentation video.

    This does not alter the frozen tracking or analyzed
    research artifacts.
    """

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    original_video = (
        job_dir
        / "input"
        / "original.mp4"
    )

    tracking_video = (
        job_dir
        / "video"
        / "tracking.mp4"
    )

    presentation_video = (
        job_dir
        / "video"
        / "presentation.mp4"
    )

    if not original_video.exists():
        raise FileNotFoundError(
            original_video
        )

    if not tracking_video.exists():
        raise FileNotFoundError(
            tracking_video
        )

    render_presentation_video(
        original_video=original_video,
        tracking_video=tracking_video,
        result_json=(
            job_dir
            / "canonical_result.json"
        ),
        output_video=presentation_video,
    )

    if not presentation_video.exists():
        raise RuntimeError(
            "Presentation renderer completed but "
            "presentation.mp4 was not created."
        )

    print(
        "Presentation video:",
        presentation_video,
    )

    return presentation_video


def finalize_job(
    *,
    job_dir: Path,
) -> dict[str, Path]:

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    print()
    print("=" * 72)
    print(
        "AUTOVUE PRODUCT FINALIZATION"
    )
    print("=" * 72)

    print(
        "Job:",
        job_dir,
    )

    print()

    canonical = (
        build_canonical_result(
            job_dir=job_dir,
        )
    )

    presentation = (
        render_job_presentation(
            job_dir=job_dir,
        )
    )

    print()
    print("=" * 72)
    print(
        "AUTOVUE FINALIZATION COMPLETE"
    )
    print("=" * 72)

    return {
        "canonical_result":
            canonical,

        "presentation_video":
            presentation,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Build canonical AutoVue result and "
            "dashboard presentation video for a product job."
        )
    )

    parser.add_argument(
        "--job-dir",
        required=True,
        type=Path,
        help="AutoVue product job directory.",
    )

    args = parser.parse_args()

    finalize_job(
        job_dir=args.job_dir,
    )


if __name__ == "__main__":
    main()
