export type EvidenceStatus =
  | "VERIFIED_FULL"
  | "CORROBORATED_FRAGMENT"
  | "NEEDS_REVIEW"
  | "REJECTED";

export interface AutoVueSummary {
  raw_tracker_ids: number;
  selected_ocr_crops: number;
  conservative_clusters: number;
  parser_valid_crop_predictions: number;
  clusters_with_complete_candidate: number;
  unique_selected_candidate_strings: number;
  verified_full: number;
  corroborated_fragment: number;
  needs_review: number;
  rejected: number;
}

export interface CandidateOption {
  plate: string;
  frame_support: number;
  track_support: number;
  mean_confidence: number | null;
  mean_correction: number | null;
  mean_quality: number | null;
  selected: boolean;
}

export interface FragmentEvidence {
  support_frame: number;
  original_track_id: number;
  source: string;
  raw_text: string;
  matching_fragment: string;
  fragment_length: number;
  required_length: number;
}

export interface Observation {
  track_id: number;
  cluster_id: number;
  frame: number;
  rank: number;
  filename: string;

  quality_score: number;
  plate_confidence: number;

  raw_0deg: string | null;
  final_raw: string | null;
  final_prediction: string | null;
  final_valid_plate: boolean;

  final_confidence: number;
  correction_cost: number | null;

  orientation_triggered: boolean;
  selected_rotation: number | null;

  preprocessing_triggered: boolean;
  selected_variant: string | null;

  total_latency_ms: number;
}

export interface ClusterResult {
  cluster_id: number;
  member_tracks: number[];

  final_candidate: string | null;

  full_frame_support: number;
  full_track_support: number;

  fragment_support_frames: number;
  fragment_support_tracks: number;

  best_fragment: string | null;
  best_fragment_length: number;

  mean_confidence: number | null;
  mean_correction: number | null;
  mean_quality: number | null;

  status: EvidenceStatus;

  candidate_options: CandidateOption[];
  fragment_evidence: FragmentEvidence[];
  observations: Observation[];
}

export interface AutoVueResult {
  schema_version: string;
  source: string;
  ground_truth_used: boolean;
  summary: AutoVueSummary;
  clusters: ClusterResult[];
}
