from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

OCR_SOURCE_DIR = (
    PROJECT_ROOT
    / "src"
    / "ocr"
)

FROZEN_M25D = (
    OCR_SOURCE_DIR
    / "m25d_final_road_ocr.py"
)


def _load_frozen_m25d() -> Any:
    """
    Load frozen M25D without modifying it.

    M25D imports its research helper modules using local
    module names such as m21_paddleocr_dev, so the frozen
    OCR source directory is temporarily exposed on sys.path.
    """

    if not FROZEN_M25D.exists():
        raise FileNotFoundError(
            FROZEN_M25D
        )

    source = FROZEN_M25D.read_text(
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
            "Frozen M25D does not contain "
            "an __main__ guard. Refusing to import it."
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            "autovue_frozen_m25d",
            FROZEN_M25D,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not create import specification "
            "for frozen M25D."
        )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    ocr_source = str(
        OCR_SOURCE_DIR
    )

    added_path = False

    if ocr_source not in sys.path:
        sys.path.insert(
            0,
            ocr_source,
        )

        added_path = True

    try:
        spec.loader.exec_module(
            module
        )

    finally:
        if (
            added_path
            and ocr_source in sys.path
        ):
            sys.path.remove(
                ocr_source
            )

    return module


def run_ocr(
    *,
    job_dir: Path,
) -> dict[str, Path]:
    """
    Execute frozen M25D OCR against one AutoVue job.

    Only filesystem locations are overridden.

    Frozen OCR behavior remains responsible for:
    - PaddleOCR
    - Indian plate-aware parsing
    - adaptive orientation rescue
    - preprocessing fallback
    - final crop prediction selection
    """

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    metadata_dir = (
        job_dir
        / "metadata"
    )

    crops_dir = (
        job_dir
        / "crops"
    )

    track_csv = (
        metadata_dir
        / "track_summary.csv"
    )

    track_map_csv = (
        metadata_dir
        / "track_to_cluster.csv"
    )

    required_inputs = (
        track_csv,
        track_map_csv,
        crops_dir,
    )

    for path in required_inputs:
        if not path.exists():
            raise FileNotFoundError(
                path
            )

    metadata_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame_csv = (
        metadata_dir
        / "frame_predictions.csv"
    )

    orientation_csv = (
        metadata_dir
        / "orientation_candidates.csv"
    )

    preprocess_csv = (
        metadata_dir
        / "preprocessing_candidates.csv"
    )

    summary_txt = (
        metadata_dir
        / "ocr_summary.txt"
    )

    module = _load_frozen_m25d()

    required_globals = (
        "TRACK_CSV",
        "TRACK_MAP_CSV",
        "CROP_DIR",
        "OUTPUT_DIR",
        "FRAME_CSV",
        "ORIENTATION_CSV",
        "PREPROCESS_CSV",
        "SUMMARY_TXT",
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
            "Frozen M25D interface changed. "
            "Missing globals: "
            + ", ".join(missing)
        )

    # -----------------------------------------------------
    # Filesystem paths ONLY.
    # OCR/parser/rescue behavior remains frozen.
    # -----------------------------------------------------

    module.TRACK_CSV = (
        track_csv
    )

    module.TRACK_MAP_CSV = (
        track_map_csv
    )

    module.CROP_DIR = (
        crops_dir
    )

    module.OUTPUT_DIR = (
        metadata_dir
    )

    module.FRAME_CSV = (
        frame_csv
    )

    module.ORIENTATION_CSV = (
        orientation_csv
    )

    module.PREPROCESS_CSV = (
        preprocess_csv
    )

    module.SUMMARY_TXT = (
        summary_txt
    )

    print()
    print("=" * 72)
    print(
        "AUTOVUE PRODUCT OCR ADAPTER"
    )
    print("=" * 72)

    print(
        "Frozen implementation:",
        FROZEN_M25D,
    )

    print(
        "Track summary:",
        track_csv,
    )

    print(
        "Track map:",
        track_map_csv,
    )

    print(
        "Plate crops:",
        crops_dir,
    )

    print()
    print(
        "Only runtime paths are overridden."
    )

    print(
        "Frozen PaddleOCR/parser/rescue "
        "behavior remains unchanged."
    )

    print()

    module.main()

    expected_outputs = {
        "frame_predictions":
            frame_csv,

        "orientation_candidates":
            orientation_csv,

        "preprocessing_candidates":
            preprocess_csv,

        "summary":
            summary_txt,
    }

    missing_outputs = [
        str(path)
        for path in expected_outputs.values()
        if not path.exists()
    ]

    if missing_outputs:
        raise RuntimeError(
            "OCR completed but required "
            "outputs are missing: "
            + ", ".join(
                missing_outputs
            )
        )

    print()
    print("=" * 72)
    print(
        "AUTOVUE OCR STAGE COMPLETE"
    )
    print("=" * 72)

    print(
        "Frame predictions:",
        frame_csv,
    )

    print(
        "Orientation candidates:",
        orientation_csv,
    )

    print(
        "Preprocessing candidates:",
        preprocess_csv,
    )

    print(
        "Summary:",
        summary_txt,
    )

    return expected_outputs


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Run frozen M25D OCR against "
            "an AutoVue product job."
        )
    )

    parser.add_argument(
        "--job-dir",
        required=True,
        type=Path,
        help="AutoVue job directory.",
    )

    args = parser.parse_args()

    run_ocr(
        job_dir=args.job_dir,
    )


if __name__ == "__main__":
    main()
