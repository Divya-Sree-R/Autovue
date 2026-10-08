from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import subprocess

import cv2
import numpy as np


STATUS_COLORS = {
    "VERIFIED_FULL": (80, 200, 80),
    "CORROBORATED_FRAGMENT": (0, 190, 255),
    "NEEDS_REVIEW": (0, 120, 255),
    "REJECTED": (150, 150, 150),
}


def _draw_alpha_box(
    frame: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    alpha: float = 0.72,
) -> None:
    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (x1, y1),
        (x2, y2),
        (18, 18, 18),
        -1,
    )

    cv2.addWeighted(
        overlay,
        alpha,
        frame,
        1 - alpha,
        0,
        frame,
    )


def _put_text(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float = 0.48,
    color: tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
) -> None:
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def load_result(
    result_path: Path,
) -> dict:
    with result_path.open(
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_timeline(
    result: dict,
) -> tuple[
    list[dict],
    dict[int, list[dict]],
]:
    """
    Build:
    1. active recognition spans
    2. observation events indexed by frame
    """

    spans = []
    observations_by_frame = defaultdict(list)

    for cluster in result["clusters"]:
        candidate = cluster.get(
            "final_candidate"
        )

        observations = cluster.get(
            "observations",
            [],
        )

        if not candidate or not observations:
            continue

        frames = [
            int(item["frame"])
            for item in observations
        ]

        spans.append(
            {
                "cluster_id":
                    cluster["cluster_id"],

                "plate":
                    candidate,

                "status":
                    cluster["status"],

                "start_frame":
                    min(frames),

                "end_frame":
                    max(frames),

                "full_support":
                    cluster[
                        "full_frame_support"
                    ],

                "fragment_support":
                    cluster[
                        "fragment_support_frames"
                    ],

                "confidence":
                    cluster.get(
                        "mean_confidence"
                    ),
            }
        )

        for observation in observations:
            event = {
                "cluster_id":
                    cluster["cluster_id"],

                "plate":
                    candidate,

                "status":
                    cluster["status"],

                "raw":
                    (
                        observation.get(
                            "final_raw"
                        )
                        or observation.get(
                            "raw_0deg"
                        )
                    ),

                "valid":
                    observation.get(
                        "final_valid_plate",
                        False,
                    ),

                "ocr_confidence":
                    observation.get(
                        "final_confidence",
                        0.0,
                    ),

                "variant":
                    observation.get(
                        "selected_variant"
                    ),
            }

            observations_by_frame[
                int(observation["frame"])
            ].append(event)

    return spans, observations_by_frame


def render_analysis_video(
    input_video: Path,
    result_json: Path,
    output_video: Path,
    presentation_mode: bool = False,
) -> None:

    result = load_result(
        result_json
    )

    spans, observations_by_frame = (
        build_timeline(result)
    )

    cap = cv2.VideoCapture(
        str(input_video)
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: "
            f"{input_video}"
        )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    total_frames = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    # -----------------------------------------------------
    # Presentation UI scaling
    #
    # Frozen/reference rendering remains exactly at 1.0.
    #
    # Product presentation videos scale their informational
    # overlays according to video resolution so text remains
    # readable on 1080p footage.
    # -----------------------------------------------------

    overlay_scale = 1.0

    if presentation_mode:

        resolution_scale = min(
            width / 768.0,
            height / 432.0,
        )

        overlay_scale = max(
            1.0,
            min(
                1.8,
                resolution_scale,
            ),
        )


    def scaled(
        value: int,
    ) -> int:

        return max(
            1,
            int(
                round(
                    value
                    * overlay_scale
                )
            ),
        )


    output_video.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_output = (
        output_video.parent
        / "autovue_result_raw.mp4"
    )

    writer = cv2.VideoWriter(
        str(raw_output),
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
            "Could not create output video."
        )

    frame_index = 0

    while True:

        ok, frame = cap.read()

        if not ok:
            break

        frame_index += 1


        # -------------------------------------------------
        # Active temporal recognition results
        # -------------------------------------------------

        active = [
            item
            for item in spans
            if (
                item["start_frame"]
                <= frame_index
                <= item["end_frame"]
            )
        ]


        if active:

            visible_count = min(
                len(active),
                3,
            )

            panel_width = scaled(
                330
            )

            panel_height = (
                scaled(38)
                + scaled(50)
                * visible_count
            )

            margin = scaled(
                10
            )

            x1 = (
                width
                - panel_width
                - margin
            )

            y1 = margin


            _draw_alpha_box(
                frame,
                x1,
                y1,
                width - margin,
                y1 + panel_height,
                alpha=0.82,
            )


            _put_text(
                frame,
                "AUTOVUE TEMPORAL RESULT",
                x1 + scaled(12),
                y1 + scaled(23),
                scale=(
                    0.42
                    * overlay_scale
                ),
                color=(
                    225,
                    225,
                    225,
                ),
                thickness=(
                    2
                    if presentation_mode
                    else 1
                ),
            )


            for index, item in enumerate(
                active[:3]
            ):

                row_y = (
                    y1
                    + scaled(50)
                    + index
                    * scaled(50)
                )

                status = item[
                    "status"
                ]

                color = (
                    STATUS_COLORS.get(
                        status,
                        (
                            255,
                            255,
                            255,
                        ),
                    )
                )


                # Product presentation mode emphasizes
                # the recognized plate itself.
                if presentation_mode:

                    main_text = (
                        f"PLATE  "
                        f"{item['plate']}"
                    )

                    detail_text = (
                        f"{status}"
                        f"  |  cluster "
                        f"#{item['cluster_id']}"
                        f"  |  full="
                        f"{item['full_support']}"
                        f"  frag="
                        f"{item['fragment_support']}"
                    )

                else:

                    main_text = (
                        f"#{item['cluster_id']} "
                        f"{item['plate']}"
                    )

                    detail_text = (
                        f"{status}  |  "
                        f"full="
                        f"{item['full_support']} "
                        f"frag="
                        f"{item['fragment_support']}"
                    )


                _put_text(
                    frame,
                    main_text,
                    x1 + scaled(12),
                    row_y,
                    scale=(
                        (
                            0.60
                            if presentation_mode
                            else 0.52
                        )
                        * overlay_scale
                    ),
                    color=(
                        255,
                        255,
                        255,
                    ),
                    thickness=(
                        2
                        if presentation_mode
                        else 2
                    ),
                )


                _put_text(
                    frame,
                    detail_text,
                    x1 + scaled(12),
                    row_y
                    + scaled(20),
                    scale=(
                        (
                            0.39
                            if presentation_mode
                            else 0.35
                        )
                        * overlay_scale
                    ),
                    color=color,
                    thickness=(
                        2
                        if presentation_mode
                        else 1
                    ),
                )


        # -------------------------------------------------
        # Exact OCR observation
        # -------------------------------------------------

        frame_events = (
            observations_by_frame.get(
                frame_index,
                [],
            )
        )


        if frame_events:

            event = (
                frame_events[0]
            )

            box_height = scaled(
                82
                if presentation_mode
                else 72
            )

            margin = scaled(
                8
            )


            _draw_alpha_box(
                frame,
                margin,
                height
                - box_height
                - margin,
                width
                - margin,
                height
                - margin,
                alpha=0.82,
            )


            status_color = (
                STATUS_COLORS.get(
                    event["status"],
                    (
                        255,
                        255,
                        255,
                    ),
                )
            )


            raw_text = (
                event["raw"]
                if event["raw"]
                else "[no OCR text]"
            )


            _put_text(
                frame,
                (
                    "OCR observation: "
                    f"{raw_text}"
                ),
                scaled(18),
                height
                - scaled(59),
                scale=(
                    0.47
                    * overlay_scale
                ),
                thickness=(
                    2
                    if presentation_mode
                    else 1
                ),
            )


            _put_text(
                frame,
                (
                    "Final plate: "
                    f"{event['plate']}"
                ),
                scaled(18),
                height
                - scaled(34),
                scale=(
                    (
                        0.58
                        if presentation_mode
                        else 0.50
                    )
                    * overlay_scale
                ),
                thickness=2,
            )


            _put_text(
                frame,
                event["status"],
                scaled(18),
                height
                - scaled(12),
                scale=(
                    0.42
                    * overlay_scale
                ),
                color=status_color,
                thickness=(
                    2
                    if presentation_mode
                    else 1
                ),
            )


        writer.write(
            frame
        )


    cap.release()
    writer.release()


    # -----------------------------------------------------
    # Browser-compatible H.264 output
    # -----------------------------------------------------

    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(raw_output),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(output_video),
    ]


    subprocess.run(
        command,
        check=True,
    )


    raw_output.unlink(
        missing_ok=True
    )


    print()
    print(
        "===== AUTOVUE VIDEO RENDERED ====="
    )

    print(
        "Input :",
        input_video,
    )

    print(
        "Result:",
        output_video,
    )

    print(
        "Frames:",
        frame_index,
    )

    print(
        "FPS   :",
        fps,
    )

    print(
        "Size  :",
        f"{width}x{height}",
    )

    print(
        "Presentation mode:",
        presentation_mode,
    )

    print(
        "Overlay scale:",
        round(
            overlay_scale,
            2,
        ),
    )

