from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import cv2

from autovue.renderer import (
    render_analysis_video,
)


# Exact frozen M25B HUD area.
#
# This is the ONLY information panel removed:
#
# Indian ANPR - Tracking
# Frame: x / total
# Tracked vehicles with plate candidate: n
#
HUD_X1 = 14
HUD_Y1 = 14
HUD_X2 = 542
HUD_Y2 = 127


def _build_clean_tracking_video(
    *,
    original_video: Path,
    tracking_video: Path,
    output_video: Path,
) -> None:
    """
    Remove only the frozen M25B tracking HUD.

    Vehicle boxes, vehicle IDs, plate boxes and plate
    confidence labels remain untouched.
    """

    original_cap = cv2.VideoCapture(
        str(original_video)
    )

    tracking_cap = cv2.VideoCapture(
        str(tracking_video)
    )

    if not original_cap.isOpened():
        raise RuntimeError(
            f"Could not open original video: "
            f"{original_video}"
        )

    if not tracking_cap.isOpened():
        raise RuntimeError(
            f"Could not open tracking video: "
            f"{tracking_video}"
        )


    width = int(
        tracking_cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        tracking_cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    fps = tracking_cap.get(
        cv2.CAP_PROP_FPS
    )


    original_width = int(
        original_cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    original_height = int(
        original_cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    original_fps = original_cap.get(
        cv2.CAP_PROP_FPS
    )


    if (
        width != original_width
        or height != original_height
    ):
        raise RuntimeError(
            "Original and tracking video dimensions "
            "do not match."
        )

    if abs(
        fps - original_fps
    ) > 0.01:
        raise RuntimeError(
            "Original and tracking video FPS "
            "do not match."
        )


    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(
            *"mp4v"
        ),
        fps,
        (
            width,
            height,
        ),
    )

    if not writer.isOpened():
        raise RuntimeError(
            "Could not create temporary clean "
            "tracking video."
        )


    frame_count = 0


    while True:

        original_ok, original_frame = (
            original_cap.read()
        )

        tracking_ok, tracking_frame = (
            tracking_cap.read()
        )


        if original_ok != tracking_ok:
            raise RuntimeError(
                "Original and tracking streams "
                "ended at different frames."
            )


        if not tracking_ok:
            break


        frame_count += 1


        x1 = max(
            0,
            HUD_X1,
        )

        y1 = max(
            0,
            HUD_Y1,
        )

        x2 = min(
            width,
            HUD_X2,
        )

        y2 = min(
            height,
            HUD_Y2,
        )


        # Remove ONLY the left M25B HUD by restoring
        # the corresponding pixels from the original.
        tracking_frame[
            y1:y2,
            x1:x2,
        ] = original_frame[
            y1:y2,
            x1:x2,
        ]


        writer.write(
            tracking_frame
        )


    original_cap.release()
    tracking_cap.release()
    writer.release()


    print(
        "Clean tracking frames:",
        frame_count,
    )


def render_presentation_video(
    *,
    original_video: Path,
    tracking_video: Path,
    result_json: Path,
    output_video: Path,
) -> None:
    """
    Build the dashboard presentation video.

    Preserves:
    - vehicle tracking boxes
    - vehicle IDs
    - plate boxes
    - PLATE confidence labels
    - AutoVue temporal-result panel
    - evidence status / full / fragment remarks
    - OCR observation information

    Removes ONLY:
    - large frozen M25B tracking HUD in the upper-left.
    """

    original_video = (
        original_video
        .expanduser()
        .resolve()
    )

    tracking_video = (
        tracking_video
        .expanduser()
        .resolve()
    )

    result_json = (
        result_json
        .expanduser()
        .resolve()
    )

    output_video = (
        output_video
        .expanduser()
        .resolve()
    )


    for path in (
        original_video,
        tracking_video,
        result_json,
    ):
        if not path.exists():
            raise FileNotFoundError(
                path
            )


    output_video.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with tempfile.TemporaryDirectory(
        prefix="autovue_presentation_"
    ) as temp_name:

        clean_tracking = (
            Path(temp_name)
            / "clean_tracking.mp4"
        )


        _build_clean_tracking_video(
            original_video=original_video,
            tracking_video=tracking_video,
            output_video=clean_tracking,
        )


        # Reapply the already-validated AutoVue
        # temporal-result and OCR evidence overlays.
        #
        # Therefore only the left tracking HUD is gone.
        render_analysis_video(
            input_video=clean_tracking,
            result_json=result_json,
            output_video=output_video,
            presentation_mode=True,
        )


    if not output_video.exists():
        raise RuntimeError(
            "Presentation video was not created."
        )


    print()
    print("=" * 72)
    print(
        "AUTOVUE PRESENTATION VIDEO COMPLETE"
    )
    print("=" * 72)

    print(
        "Original:",
        original_video,
    )

    print(
        "Tracking:",
        tracking_video,
    )

    print(
        "Result  :",
        result_json,
    )

    print(
        "Output  :",
        output_video,
    )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Create AutoVue presentation video "
            "while removing only the M25B "
            "tracking information HUD."
        )
    )

    parser.add_argument(
        "--original",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--tracking",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--result",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )


    args = parser.parse_args()


    render_presentation_video(
        original_video=args.original,
        tracking_video=args.tracking,
        result_json=args.result,
        output_video=args.output,
    )


if __name__ == "__main__":
    main()
