"""Product deployment settings; local defaults preserve the existing app."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path(name: str, default: Path) -> Path:
    # Preserve venv executable symlinks: resolving bin/python selects the base
    # interpreter and silently drops the environment's installed dependencies.
    return Path(os.environ.get(name, str(default))).expanduser().absolute()


JOBS_ROOT = _path("AUTOVUE_JOBS_ROOT", PROJECT_ROOT / "app_data" / "jobs")
MAIN_PYTHON = _path("AUTOVUE_MAIN_PYTHON", PROJECT_ROOT / ".venv" / "bin" / "python")
PADDLE_PYTHON = _path(
    "AUTOVUE_PADDLE_PYTHON", PROJECT_ROOT / ".venv_paddleocr" / "bin" / "python"
)
FROZEN_OUTPUT_ROOT = _path(
    "AUTOVUE_FROZEN_OUTPUT_ROOT", PROJECT_ROOT / "outputs" / "M25_final_road_eval"
)
ORIGINAL_VIDEO = _path(
    "AUTOVUE_REFERENCE_ORIGINAL_VIDEO",
    PROJECT_ROOT / "data" / "raw" / "final_road_eval" / "road_eval.mp4",
)
TRACKING_VIDEO = _path(
    "AUTOVUE_REFERENCE_TRACKING_VIDEO",
    FROZEN_OUTPUT_ROOT / "M25B_tracking" / "tracking_best_plate.mp4",
)
ANALYZED_VIDEO = _path(
    "AUTOVUE_REFERENCE_ANALYZED_VIDEO", JOBS_ROOT / "m25_reference" / "video" / "autovue_result.mp4"
)
PRESENTATION_VIDEO = _path(
    "AUTOVUE_REFERENCE_PRESENTATION_VIDEO", JOBS_ROOT / "m25_reference" / "video" / "presentation.mp4"
)
CROP_DIR = _path(
    "AUTOVUE_REFERENCE_CROP_DIR", FROZEN_OUTPUT_ROOT / "M25B_tracking" / "best_plate_crops"
)

# Empty means API-only, as before. Production supplies the compiled React path.
FRONTEND_DIST = (
    Path(os.environ["AUTOVUE_FRONTEND_DIST"]).expanduser().resolve()
    if os.environ.get("AUTOVUE_FRONTEND_DIST")
    else None
)
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "AUTOVUE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
REQUIRE_AUTH = os.environ.get("AUTOVUE_REQUIRE_AUTH", "").lower() in {
    "1", "true", "yes", "on"
}
AUTH_USERNAME = os.environ.get("AUTOVUE_AUTH_USERNAME", "")
AUTH_PASSWORD = os.environ.get("AUTOVUE_AUTH_PASSWORD", "")
