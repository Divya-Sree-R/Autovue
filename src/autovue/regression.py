from pathlib import Path
import json
import sys

from autovue.result_loader import (
    load_frozen_m25_result,
)


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PATH = (
    ROOT
    / "tests"
    / "regression"
    / "m25e_expected.json"
)

OUTPUT_ROOT = (
    ROOT
    / "outputs"
    / "M25_final_road_eval"
)

CANONICAL_OUTPUT = (
    ROOT
    / "app_data"
    / "jobs"
    / "m25_reference"
    / "canonical_result.json"
)


def main() -> int:
    with EXPECTED_PATH.open(
        encoding="utf-8"
    ) as file:
        expected = json.load(file)

    result = load_frozen_m25_result(
        OUTPUT_ROOT
    )

    actual = result.to_dict()
    summary = actual["summary"]

    checks = {
        "raw_tracker_ids":
            summary["raw_tracker_ids"],

        "selected_ocr_crops":
            summary["selected_ocr_crops"],

        "conservative_clusters":
            summary["conservative_clusters"],

        "parser_valid_crop_predictions":
            summary[
                "parser_valid_crop_predictions"
            ],

        "clusters_with_complete_candidate":
            summary[
                "clusters_with_complete_candidate"
            ],

        "unique_selected_candidate_strings":
            summary[
                "unique_selected_candidate_strings"
            ],
    }

    expected_statuses = expected["statuses"]

    status_checks = {
        "VERIFIED_FULL":
            summary["verified_full"],

        "CORROBORATED_FRAGMENT":
            summary[
                "corroborated_fragment"
            ],

        "NEEDS_REVIEW":
            summary["needs_review"],

        "REJECTED":
            summary["rejected"],
    }

    failures = []

    print(
        "\n===== AUTOVUE M25 REGRESSION ====="
    )

    for key, actual_value in checks.items():
        expected_value = expected[key]

        ok = actual_value == expected_value

        print(
            f"{key:38} "
            f"expected={expected_value:<5} "
            f"actual={actual_value:<5} "
            f"{'PASS' if ok else 'FAIL'}"
        )

        if not ok:
            failures.append(key)

    print(
        "\n===== EVIDENCE STATUS ====="
    )

    for key, actual_value in (
        status_checks.items()
    ):
        expected_value = (
            expected_statuses[key]
        )

        ok = actual_value == expected_value

        print(
            f"{key:38} "
            f"expected={expected_value:<5} "
            f"actual={actual_value:<5} "
            f"{'PASS' if ok else 'FAIL'}"
        )

        if not ok:
            failures.append(key)

    if failures:
        print(
            "\nREGRESSION FAILED."
        )

        print(
            "Changed fields:",
            ", ".join(failures),
        )

        return 1

    CANONICAL_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with CANONICAL_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            actual,
            file,
            indent=2,
        )

    print(
        "\nREGRESSION PASSED."
    )

    print(
        "Canonical result:",
        CANONICAL_OUTPUT,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
