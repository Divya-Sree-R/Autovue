from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FROZEN_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "M25_final_road_eval"
)

ORIGINAL_VIDEO = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "final_road_eval"
    / "road_eval.mp4"
)

TRACKING_VIDEO = (
    FROZEN_OUTPUT_ROOT
    / "M25B_tracking"
    / "tracking_best_plate.mp4"
)

ANALYZED_VIDEO = (
    PROJECT_ROOT
    / "app_data"
    / "jobs"
    / "m25_reference"
    / "video"
    / "autovue_result.mp4"
)

CROP_DIR = (
    FROZEN_OUTPUT_ROOT
    / "M25B_tracking"
    / "best_plate_crops"
)
