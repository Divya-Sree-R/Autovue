# AutoVue Frozen Research Pipeline

The M26 application layer must preserve the behavior of the completed
M25 research pipeline.

## Frozen stages

- M25B:
  `src/tracking/m25b_final_road_tracking.py`
  - vehicle detection
  - BoT-SORT tracking
  - vehicle ROI
  - plate detection
  - quality-ranked Top-K plate crops

- M25C:
  `src/tracking/m25c_track_reassociation.py`
  - conservative tracker reassociation

- M25D:
  `src/ocr/m25d_final_road_ocr.py`
  - PaddleOCR
  - Indian registration parser
  - adaptive orientation rescue
  - road preprocessing fallback

- M25E:
  `src/ocr/m25e_final_temporal_consensus.py`
  - complete-candidate ranking
  - fragment corroboration
  - evidence-status assignment

## Regression target

For the frozen M25 unseen road video, the productized pipeline must reproduce:

- 45 raw tracker IDs
- 92 selected OCR crops
- 43 conservative clusters
- 15 parser-valid crop predictions
- 8 clusters with complete candidates
- 6 unique selected candidate strings
- 2 VERIFIED_FULL
- 2 CORROBORATED_FRAGMENT
- 4 NEEDS_REVIEW
- 35 REJECTED

These are automatic evidence outcomes, not ground-truth accuracy metrics.

No M25 threshold, parser rule, OCR rule, reassociation rule, or temporal-consensus
rule should be modified merely to make the new application layer work.
