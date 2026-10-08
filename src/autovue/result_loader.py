from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv

from autovue.schemas import (
    AutoVueResult,
    AutoVueSummary,
    CandidateOption,
    ClusterResult,
    FragmentEvidence,
    Observation,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required AutoVue artifact not found: {path}"
        )

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def _text(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()
    return value if value else None


def _int(
    value: str | None,
    default: int = 0,
) -> int:
    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    try:
        return int(float(value))
    except ValueError:
        return default


def _float(
    value: str | None,
) -> float | None:
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _bool(value: str | None) -> bool:
    if value is None:
        return False

    value = value.strip().lower()

    if value in {
        "",
        "false",
        "0",
        "none",
        "null",
        "nan",
        "no",
    }:
        return False

    return True


def _member_tracks(
    value: str | None,
) -> list[int]:
    if not value:
        return []

    return [
        int(part.strip())
        for part in value.split("|")
        if part.strip()
    ]


def load_frozen_m25_result(
    output_root: Path,
) -> AutoVueResult:

    track_rows = _read_csv(
        output_root
        / "M25B_tracking"
        / "track_summary.csv"
    )

    frame_rows = _read_csv(
        output_root
        / "M25D_frame_predictions.csv"
    )

    candidate_rows = _read_csv(
        output_root
        / "M25E_candidate_options.csv"
    )

    fragment_rows = _read_csv(
        output_root
        / "M25E_fragment_evidence.csv"
    )

    consensus_rows = _read_csv(
        output_root
        / "M25E_cluster_consensus.csv"
    )

    observations_by_cluster: dict[
        int,
        list[Observation],
    ] = defaultdict(list)

    candidates_by_cluster: dict[
        int,
        list[CandidateOption],
    ] = defaultdict(list)

    fragments_by_cluster: dict[
        int,
        list[FragmentEvidence],
    ] = defaultdict(list)

    # ---------------------------------------------------------
    # M25D observations
    # ---------------------------------------------------------
    for row in frame_rows:
        correction = _int(
            row.get("correction_cost"),
            default=-1,
        )

        observation = Observation(
            track_id=_int(row.get("track_id")),
            cluster_id=_int(row.get("cluster_id")),
            frame=_int(row.get("frame")),
            rank=_int(row.get("rank")),
            filename=row.get("filename", ""),
            quality_score=(
                _float(row.get("quality_score"))
                or 0.0
            ),
            plate_confidence=(
                _float(row.get("plate_confidence"))
                or 0.0
            ),
            raw_0deg=_text(
                row.get("raw_0deg")
            ),
            final_raw=_text(
                row.get("final_raw")
            ),
            final_prediction=_text(
                row.get("final_prediction")
            ),
            final_valid_plate=_bool(
                row.get("final_valid_plate")
            ),
            final_confidence=(
                _float(row.get("final_confidence"))
                or 0.0
            ),
            correction_cost=(
                None
                if correction < 0
                else correction
            ),
            orientation_triggered=_bool(
                row.get("orientation_triggered")
            ),
            selected_rotation=(
                _int(row.get("selected_rotation"))
                if _text(
                    row.get("selected_rotation")
                )
                is not None
                else None
            ),
            preprocessing_triggered=_bool(
                row.get("preprocessing_triggered")
            ),
            selected_variant=_text(
                row.get("selected_variant")
            ),
            total_latency_ms=(
                _float(row.get("total_latency_ms"))
                or 0.0
            ),
        )

        observations_by_cluster[
            observation.cluster_id
        ].append(observation)

    # ---------------------------------------------------------
    # M25E candidate options
    # ---------------------------------------------------------
    for row in candidate_rows:
        cluster_id = _int(
            row.get("cluster_id")
        )

        candidates_by_cluster[
            cluster_id
        ].append(
            CandidateOption(
                plate=row.get(
                    "plate",
                    "",
                ).strip(),
                frame_support=_int(
                    row.get("frame_support")
                ),
                track_support=_int(
                    row.get("track_support")
                ),
                mean_confidence=_float(
                    row.get("mean_confidence")
                ),
                mean_correction=_float(
                    row.get("mean_correction")
                ),
                mean_quality=_float(
                    row.get("mean_quality")
                ),
                selected=_bool(
                    row.get("selected")
                ),
            )
        )

    # ---------------------------------------------------------
    # M25E fragment evidence
    # ---------------------------------------------------------
    for row in fragment_rows:
        cluster_id = _int(
            row.get("cluster_id")
        )

        fragments_by_cluster[
            cluster_id
        ].append(
            FragmentEvidence(
                support_frame=_int(
                    row.get("support_frame")
                ),
                original_track_id=_int(
                    row.get(
                        "original_track_id"
                    )
                ),
                source=row.get(
                    "source",
                    "",
                ).strip(),
                raw_text=row.get(
                    "raw_text",
                    "",
                ).strip(),
                matching_fragment=row.get(
                    "matching_fragment",
                    "",
                ).strip(),
                fragment_length=_int(
                    row.get("fragment_length")
                ),
                required_length=_int(
                    row.get("required_length")
                ),
            )
        )

    # ---------------------------------------------------------
    # M25E final cluster consensus
    # ---------------------------------------------------------
    clusters: list[ClusterResult] = []

    for row in consensus_rows:
        cluster_id = _int(
            row.get("cluster_id")
        )

        clusters.append(
            ClusterResult(
                cluster_id=cluster_id,
                member_tracks=_member_tracks(
                    row.get("member_tracks")
                ),
                final_candidate=_text(
                    row.get("final_candidate")
                ),
                full_frame_support=_int(
                    row.get(
                        "full_frame_support"
                    )
                ),
                full_track_support=_int(
                    row.get(
                        "full_track_support"
                    )
                ),
                fragment_support_frames=_int(
                    row.get(
                        "fragment_support_frames"
                    )
                ),
                fragment_support_tracks=_int(
                    row.get(
                        "fragment_support_tracks"
                    )
                ),
                best_fragment=_text(
                    row.get("best_fragment")
                ),
                best_fragment_length=_int(
                    row.get(
                        "best_fragment_length"
                    )
                ),
                mean_confidence=_float(
                    row.get("mean_confidence")
                ),
                mean_correction=_float(
                    row.get("mean_correction")
                ),
                mean_quality=_float(
                    row.get("mean_quality")
                ),
                status=row.get(
                    "status",
                    "",
                ).strip(),

                candidate_options=sorted(
                    candidates_by_cluster.get(
                        cluster_id,
                        [],
                    ),
                    key=lambda item: (
                        not item.selected,
                        -item.frame_support,
                    ),
                ),

                fragment_evidence=sorted(
                    fragments_by_cluster.get(
                        cluster_id,
                        [],
                    ),
                    key=lambda item:
                    item.support_frame,
                ),

                observations=sorted(
                    observations_by_cluster.get(
                        cluster_id,
                        [],
                    ),
                    key=lambda item: (
                        item.frame,
                        item.rank,
                    ),
                ),
            )
        )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------
    status_counts = Counter(
        cluster.status
        for cluster in clusters
    )

    raw_tracker_ids = {
        _int(row.get("track_id"))
        for row in track_rows
    }

    valid_predictions = sum(
        1
        for row in frame_rows
        if _bool(
            row.get("final_valid_plate")
        )
    )

    complete_clusters = [
        cluster
        for cluster in clusters
        if cluster.final_candidate
    ]

    unique_candidates = {
        cluster.final_candidate
        for cluster in complete_clusters
        if cluster.final_candidate
    }

    summary = AutoVueSummary(
        raw_tracker_ids=len(
            raw_tracker_ids
        ),
        selected_ocr_crops=len(
            track_rows
        ),
        conservative_clusters=len(
            clusters
        ),
        parser_valid_crop_predictions=(
            valid_predictions
        ),
        clusters_with_complete_candidate=(
            len(complete_clusters)
        ),
        unique_selected_candidate_strings=(
            len(unique_candidates)
        ),
        verified_full=status_counts.get(
            "VERIFIED_FULL",
            0,
        ),
        corroborated_fragment=(
            status_counts.get(
                "CORROBORATED_FRAGMENT",
                0,
            )
        ),
        needs_review=status_counts.get(
            "NEEDS_REVIEW",
            0,
        ),
        rejected=status_counts.get(
            "REJECTED",
            0,
        ),
    )

    return AutoVueResult(
        schema_version="1.1",
        source="M25_frozen_unseen_road",
        ground_truth_used=False,
        summary=summary,
        clusters=clusters,
    )
