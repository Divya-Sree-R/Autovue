from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Observation:
    track_id: int
    cluster_id: int
    frame: int
    rank: int
    filename: str

    quality_score: float
    plate_confidence: float

    raw_0deg: str | None
    final_raw: str | None
    final_prediction: str | None
    final_valid_plate: bool

    final_confidence: float
    correction_cost: int | None

    orientation_triggered: bool
    selected_rotation: int | None

    preprocessing_triggered: bool
    selected_variant: str | None

    total_latency_ms: float


@dataclass
class CandidateOption:
    plate: str
    frame_support: int
    track_support: int
    mean_confidence: float | None
    mean_correction: float | None
    mean_quality: float | None
    selected: bool


@dataclass
class FragmentEvidence:
    support_frame: int
    original_track_id: int
    source: str
    raw_text: str
    matching_fragment: str
    fragment_length: int
    required_length: int


@dataclass
class ClusterResult:
    cluster_id: int
    member_tracks: list[int]

    final_candidate: str | None

    full_frame_support: int
    full_track_support: int

    fragment_support_frames: int
    fragment_support_tracks: int

    best_fragment: str | None
    best_fragment_length: int

    mean_confidence: float | None
    mean_correction: float | None
    mean_quality: float | None

    status: str

    candidate_options: list[CandidateOption] = field(
        default_factory=list
    )

    fragment_evidence: list[FragmentEvidence] = field(
        default_factory=list
    )

    observations: list[Observation] = field(
        default_factory=list
    )


@dataclass
class AutoVueSummary:
    raw_tracker_ids: int
    selected_ocr_crops: int
    conservative_clusters: int
    parser_valid_crop_predictions: int
    clusters_with_complete_candidate: int
    unique_selected_candidate_strings: int

    verified_full: int
    corroborated_fragment: int
    needs_review: int
    rejected: int


@dataclass
class AutoVueResult:
    schema_version: str
    source: str
    ground_truth_used: bool

    summary: AutoVueSummary
    clusters: list[ClusterResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
