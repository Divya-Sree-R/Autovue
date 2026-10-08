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

FROZEN_M25E = (
    OCR_SOURCE_DIR
    / "m25e_final_temporal_consensus.py"
)


def _load_frozen_m25e() -> Any:
    """
    Load the frozen M25E temporal-consensus script.

    Only runtime filesystem locations will be replaced.
    Candidate voting, fragment corroboration and evidence
    status logic remain unchanged.
    """

    if not FROZEN_M25E.exists():
        raise FileNotFoundError(
            FROZEN_M25E
        )

    source = FROZEN_M25E.read_text(
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
            "Frozen M25E does not contain an "
            "__main__ guard. Refusing to import it."
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            "autovue_frozen_m25e",
            FROZEN_M25E,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not create import specification "
            "for frozen M25E."
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


def run_consensus(
    *,
    job_dir: Path,
) -> dict[str, Path]:
    """
    Run frozen M25E temporal consensus for one AutoVue job.

    Inputs:
    - frame predictions
    - preprocessing candidates
    - conservative track map

    Outputs:
    - candidate options
    - fragment evidence
    - cluster consensus
    - summary
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

    frame_csv = (
        metadata_dir
        / "frame_predictions.csv"
    )

    preprocess_csv = (
        metadata_dir
        / "preprocessing_candidates.csv"
    )

    track_map_csv = (
        metadata_dir
        / "track_to_cluster.csv"
    )

    for path in (
        frame_csv,
        preprocess_csv,
        track_map_csv,
    ):
        if not path.exists():
            raise FileNotFoundError(
                path
            )

    candidate_options = (
        metadata_dir
        / "candidate_options.csv"
    )

    fragment_evidence = (
        metadata_dir
        / "fragment_evidence.csv"
    )

    cluster_consensus = (
        metadata_dir
        / "cluster_consensus.csv"
    )

    summary_txt = (
        metadata_dir
        / "temporal_consensus_summary.txt"
    )

    module = _load_frozen_m25e()

    required_globals = (
        "FRAME_CSV",
        "PREPROCESS_CSV",
        "TRACK_MAP_CSV",
        "OUTPUT_DIR",
        "OPTIONS_CSV",
        "EVIDENCE_CSV",
        "CONSENSUS_CSV",
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
            "Frozen M25E interface changed. "
            "Missing globals: "
            + ", ".join(missing)
        )

    # Filesystem locations ONLY.
    module.FRAME_CSV = (
        frame_csv
    )

    module.PREPROCESS_CSV = (
        preprocess_csv
    )

    module.TRACK_MAP_CSV = (
        track_map_csv
    )

    module.OUTPUT_DIR = (
        metadata_dir
    )

    module.OPTIONS_CSV = (
        candidate_options
    )

    module.EVIDENCE_CSV = (
        fragment_evidence
    )

    module.CONSENSUS_CSV = (
        cluster_consensus
    )

    module.SUMMARY_TXT = (
        summary_txt
    )

    print()
    print("=" * 72)
    print(
        "AUTOVUE PRODUCT TEMPORAL CONSENSUS ADAPTER"
    )
    print("=" * 72)

    print(
        "Frozen implementation:",
        FROZEN_M25E,
    )

    print(
        "Frame predictions:",
        frame_csv,
    )

    print(
        "Track map:",
        track_map_csv,
    )

    print()
    print(
        "Only runtime paths are overridden."
    )

    print(
        "Frozen voting, fragment corroboration "
        "and evidence-status rules remain unchanged."
    )

    print()

    module.main()

    expected_outputs = {
        "candidate_options":
            candidate_options,

        "fragment_evidence":
            fragment_evidence,

        "cluster_consensus":
            cluster_consensus,

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
            "Temporal consensus completed but "
            "required outputs are missing: "
            + ", ".join(
                missing_outputs
            )
        )

    print()
    print("=" * 72)
    print(
        "AUTOVUE TEMPORAL CONSENSUS COMPLETE"
    )
    print("=" * 72)

    print(
        "Candidate options:",
        candidate_options,
    )

    print(
        "Fragment evidence:",
        fragment_evidence,
    )

    print(
        "Cluster consensus:",
        cluster_consensus,
    )

    return expected_outputs


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Run frozen M25E temporal consensus "
            "against an AutoVue product job."
        )
    )

    parser.add_argument(
        "--job-dir",
        required=True,
        type=Path,
        help="AutoVue job directory.",
    )

    args = parser.parse_args()

    run_consensus(
        job_dir=args.job_dir,
    )


if __name__ == "__main__":
    main()
