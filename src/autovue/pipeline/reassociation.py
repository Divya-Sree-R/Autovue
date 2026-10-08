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

FROZEN_M25C = (
    PROJECT_ROOT
    / "src"
    / "tracking"
    / "m25c_track_reassociation.py"
)


def _load_frozen_m25c() -> Any:
    """
    Load frozen M25C without modifying or executing it
    automatically.

    Productization changes filesystem paths only.
    """

    if not FROZEN_M25C.exists():
        raise FileNotFoundError(
            FROZEN_M25C
        )

    source = FROZEN_M25C.read_text(
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
            "Frozen M25C does not contain "
            "an __main__ guard. Refusing to "
            "import it automatically."
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            "autovue_frozen_m25c",
            FROZEN_M25C,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not create import "
            "specification for frozen M25C."
        )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    return module


def run_reassociation(
    *,
    job_dir: Path,
) -> dict[str, Path]:
    """
    Run frozen M25C conservative reassociation
    against one AutoVue product job.

    Only filesystem paths are overridden.

    The frozen merge rule remains unchanged:
    - different tracker IDs
    - exact same saved crop bytes
    - same frame

    OCR and ground truth are not used.
    """

    job_dir = (
        job_dir
        .expanduser()
        .resolve()
    )

    track_summary = (
        job_dir
        / "metadata"
        / "track_summary.csv"
    )

    crops_dir = (
        job_dir
        / "crops"
    )

    metadata_dir = (
        job_dir
        / "metadata"
    )

    if not track_summary.exists():
        raise FileNotFoundError(
            track_summary
        )

    if not crops_dir.exists():
        raise FileNotFoundError(
            crops_dir
        )

    metadata_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    duplicate_csv = (
        metadata_dir
        / "duplicate_track_pairs.csv"
    )

    merged_csv = (
        metadata_dir
        / "merged_clusters.csv"
    )

    track_map_csv = (
        metadata_dir
        / "track_to_cluster.csv"
    )

    summary_txt = (
        metadata_dir
        / "track_reassociation_summary.txt"
    )

    module = _load_frozen_m25c()

    required_globals = (
        "TRACK_CSV",
        "CROP_DIR",
        "OUTPUT_DIR",
        "DUPLICATE_CSV",
        "MERGED_CLUSTER_CSV",
        "TRACK_MAP_CSV",
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
            "Frozen M25C interface changed. "
            "Missing globals: "
            + ", ".join(missing)
        )

    # -----------------------------------------------------
    # Change filesystem paths ONLY.
    # Do not change UnionFind logic or merge criteria.
    # -----------------------------------------------------

    module.TRACK_CSV = (
        track_summary
    )

    module.CROP_DIR = (
        crops_dir
    )

    module.OUTPUT_DIR = (
        metadata_dir
    )

    module.DUPLICATE_CSV = (
        duplicate_csv
    )

    module.MERGED_CLUSTER_CSV = (
        merged_csv
    )

    module.TRACK_MAP_CSV = (
        track_map_csv
    )

    module.SUMMARY_TXT = (
        summary_txt
    )

    print()
    print("=" * 72)
    print(
        "AUTOVUE PRODUCT REASSOCIATION ADAPTER"
    )
    print("=" * 72)

    print(
        "Frozen implementation:",
        FROZEN_M25C,
    )

    print(
        "Track summary:",
        track_summary,
    )

    print(
        "Crops:",
        crops_dir,
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
        "Frozen conservative merge rule "
        "remains unchanged."
    )

    print()

    module.main()

    expected_outputs = {
        "duplicate_pairs":
            duplicate_csv,

        "merged_clusters":
            merged_csv,

        "track_to_cluster":
            track_map_csv,

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
            "Reassociation completed but "
            "required outputs are missing: "
            + ", ".join(
                missing_outputs
            )
        )

    print()
    print("=" * 72)
    print(
        "AUTOVUE REASSOCIATION STAGE COMPLETE"
    )
    print("=" * 72)

    print(
        "Track map:",
        track_map_csv,
    )

    print(
        "Merged clusters:",
        merged_csv,
    )

    print(
        "Duplicate evidence:",
        duplicate_csv,
    )

    return expected_outputs


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Run frozen M25C conservative "
            "track reassociation for an "
            "AutoVue product job."
        )
    )

    parser.add_argument(
        "--job-dir",
        required=True,
        type=Path,
        help="AutoVue job directory.",
    )

    args = parser.parse_args()

    run_reassociation(
        job_dir=args.job_dir,
    )


if __name__ == "__main__":
    main()
