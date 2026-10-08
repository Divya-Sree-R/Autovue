from pathlib import Path

from autovue.renderer import (
    render_analysis_video,
)


ROOT = Path(__file__).resolve().parents[2]

INPUT_VIDEO = (
    ROOT
    / "outputs"
    / "M25_final_road_eval"
    / "M25B_tracking"
    / "tracking_best_plate.mp4"
)

RESULT_JSON = (
    ROOT
    / "app_data"
    / "jobs"
    / "m25_reference"
    / "canonical_result.json"
)

OUTPUT_VIDEO = (
    ROOT
    / "app_data"
    / "jobs"
    / "m25_reference"
    / "video"
    / "autovue_result.mp4"
)


def main() -> None:
    render_analysis_video(
        input_video=INPUT_VIDEO,
        result_json=RESULT_JSON,
        output_video=OUTPUT_VIDEO,
    )


if __name__ == "__main__":
    main()
