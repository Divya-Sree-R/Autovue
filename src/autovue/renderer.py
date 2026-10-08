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
) -> None:

    result = load_result(
        result_json
    )

    summary = result["summary"]

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
        (width, height),
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

        current_time = (
            frame_index / fps
            if fps > 0
            else 0
        )

        # -------------------------------------------------
        # AutoVue temporal result panel
        #
        # The frozen M25B video already contains its own
        # frame/tracking HUD in the upper-left corner.
        # We therefore avoid placing another full-width HUD
        # over it.
        # -------------------------------------------------
        # -------------------------------------------------
        # Active final recognition results
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
            panel_height = (
                31
                + 39 * min(
                    len(active),
                    3,
                )
            )

            panel_width = 305

            x1 = (
                width
                - panel_width
                - 8
            )

            y1 = 10

            _draw_alpha_box(
                frame,
                x1,
                y1,
                width - 8,
                y1 + panel_height,
                alpha=0.78,
            )

            _put_text(
                frame,
                "AUTOVUE TEMPORAL RESULT",
                x1 + 10,
                y1 + 20,
                scale=0.42,
                color=(220, 220, 220),
                thickness=1,
            )

            for index, item in enumerate(
                active[:3]
            ):
                y = (
                    y1
                    + 45
                    + index * 39
                )

                status = item["status"]

                color = (
                    STATUS_COLORS.get(
                        status,
                        (255, 255, 255),
                    )
                )

                _put_text(
                    frame,
                    (
                        f"#{item['cluster_id']} "
                        f"{item['plate']}"
                    ),
                    x1 + 10,
                    y,
                    scale=0.52,
                    color=(255, 255, 255),
                    thickness=2,
                )

                _put_text(
                    frame,
                    (
                        f"{status}  |  "
                        f"full={item['full_support']} "
                        f"frag={item['fragment_support']}"
                    ),
                    x1 + 10,
                    y + 18,
                    scale=0.35,
                    color=color,
                    thickness=1,
                )

        # -------------------------------------------------
        # Exact OCR observation event
        # -------------------------------------------------
        frame_events = (
            observations_by_frame.get(
                frame_index,
                [],
            )
        )

        if frame_events:
            event = frame_events[0]

            box_height = 72

            _draw_alpha_box(
                frame,
                8,
                height - box_height - 8,
                width - 8,
                height - 8,
                alpha=0.80,
            )

            status_color = (
                STATUS_COLORS.get(
                    event["status"],
                    (255, 255, 255),
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
                    f"OCR observation: "
                    f"{raw_text}"
                ),
                18,
                height - 54,
                scale=0.46,
            )

            _put_text(
                frame,
                (
                    f"Final plate: "
                    f"{event['plate']}"
                ),
                18,
                height - 32,
                scale=0.50,
                thickness=2,
            )

            _put_text(
                frame,
                event["status"],
                18,
                height - 12,
                scale=0.40,
                color=status_color,
                thickness=1,
            )

        writer.write(frame)

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
    print("===== AUTOVUE VIDEO RENDERED =====")
    print("Input :", input_video)
    print("Result:", output_video)
    print("Frames:", frame_index)
    print("FPS   :", fps)
    print(
        "Size  :",
        f"{width}x{height}",
    )
