from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

FROZEN_M25B = (
    PROJECT_ROOT
    / "src"
    / "tracking"
    / "m25b_final_road_tracking.py"
)


def _load_frozen_m25b() -> Any:
    """
    Load the frozen M25B module without editing it.

    We require an __main__ guard before importing so that
    importing the module cannot accidentally start inference.
    """

    if not FROZEN_M25B.exists():
        raise FileNotFoundError(
            FROZEN_M25B
        )

    source = FROZEN_M25B.read_text(
        encoding="utf-8"
    )

    guards = (
        'if __name__ == "__main__":',
        "if __name__ == '__main__':",
    )

    if not any(
        guard in source
        for guard in guards
    ):
        raise RuntimeError(
            "Frozen M25B script does not contain "
            "an __main__ guard. Refusing to import "
            "it automatically."
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            "autovue_frozen_m25b",
            FROZEN_M25B,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not create import specification "
            "for frozen M25B."
        )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    return module


def run_tracking(
    *,
    input_video: Path,
    job_dir: Path,
) -> dict[str, Path]:
    """
    Run the unchanged frozen M25B tracking logic using
    job-specific input/output paths.

    Algorithmic parameters are NOT overridden.
    Only filesystem locations are replaced.
    """

    input_video = (
        input_video
        .expanduser()
        .resolve()
    )

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    if not input_video.exists():
        raise FileNotFoundError(
            input_video
        )

    crops_dir = (
        job_dir
        / "crops"
    )

    metadata_dir = (
        job_dir
        / "metadata"
    )

    video_dir = (
        job_dir
        / "video"
    )

    crops_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    video_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    tracking_video = (
        video_dir
        / "tracking.mp4"
    )

    track_summary = (
        metadata_dir
        / "track_summary.csv"
    )

    module = _load_frozen_m25b()

    required_globals = (
        "INPUT_VIDEO",
        "OUTPUT_DIR",
        "OUTPUT_VIDEO",
        "BEST_CROP_DIR",
        "SUMMARY_CSV",
        "main",
    )

    missing = [
        name
        for name in required_globals
        if not hasattr(
            module,
            name,
        )
    ]

    if missing:
        raise RuntimeError(
            "Frozen M25B interface changed. "
            "Missing globals: "
            + ", ".join(missing)
        )

    # -----------------------------------------------------
    # IMPORTANT:
    # Change only filesystem paths.
    #
    # Do NOT override:
    # VEHICLE_MODEL
    # VEHICLE_CLASSES
    # VEHICLE_CONF
    # PLATE_CONF
    # PLATE_IOU
    # VEHICLE_IMGSZ
    # PLATE_IMGSZ
    # MIN_PLATE_WIDTH
    # MIN_PLATE_HEIGHT
    # MIN_ASPECT_RATIO
    # MAX_ASPECT_RATIO
    # TOP_K_CANDIDATES
    # MIN_FRAME_GAP
    # -----------------------------------------------------

    module.INPUT_VIDEO = (
        input_video
    )

    module.OUTPUT_DIR = (
        job_dir
    )

    module.OUTPUT_VIDEO = (
        tracking_video
    )

    module.BEST_CROP_DIR = (
        crops_dir
    )

    module.SUMMARY_CSV = (
        track_summary
    )

    print()
    print(
        "=" * 72
    )
    print(
        "AUTOVUE PRODUCT TRACKING ADAPTER"
    )
    print(
        "=" * 72
    )
    print(
        "Frozen implementation:",
        FROZEN_M25B,
    )
    print(
        "Input:",
        input_video,
    )
    print(
        "Job:",
        job_dir,
    )
    print()
    print(
        "Only runtime paths are overridden."
    )
    print(
        "Frozen M25B algorithmic parameters "
        "remain unchanged."
    )
    print()

    module.main()

    expected_outputs = {
        "tracking_video":
            tracking_video,

        "track_summary":
            track_summary,

        "crops_dir":
            crops_dir,
    }

    missing_outputs = [
        str(path)
        for path in (
            tracking_video,
            track_summary,
        )
        if not path.exists()
    ]

    if missing_outputs:
        raise RuntimeError(
            "Tracking stage finished but required "
            "outputs are missing: "
            + ", ".join(
                missing_outputs
            )
        )

    crop_count = sum(
        1
        for path in crops_dir.iterdir()
        if path.is_file()
    )

    print()
    print(
        "=" * 72
    )
    print(
        "AUTOVUE TRACKING STAGE COMPLETE"
    )
    print(
        "=" * 72
    )
    print(
        "Tracking video:",
        tracking_video,
    )
    print(
        "Track summary:",
        track_summary,
    )
    print(
        "Saved crops:",
        crop_count,
    )

    return expected_outputs


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Run frozen M25B tracking logic "
            "against an AutoVue product job."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input MP4 video.",
    )

    parser.add_argument(
        "--job-dir",
        required=True,
        type=Path,
        help="AutoVue job directory.",
    )

    args = parser.parse_args()

    run_tracking(
        input_video=args.input,
        job_dir=args.job_dir,
    )


if __name__ == "__main__":
    main()
