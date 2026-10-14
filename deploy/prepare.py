"""Verify the frozen baseline and stage only required deployment assets.

Run with the existing local environment: .venv/bin/python -B deploy/prepare.py
Assets stay in ignored app_data/deploy; no original artifact is overwritten.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name('baseline.json')


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify():
    baseline = json.loads(MANIFEST.read_text())
    for relative, expected in baseline['protected_files'].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f'Protected baseline changed: {relative}')
    paddle_cache = Path(os.environ.get('AUTOVUE_PADDLE_CACHE', Path.home() / '.paddlex'))
    for relative, expected in baseline['paddle_assets'].items():
        if digest(paddle_cache / relative) != expected:
            raise RuntimeError(f'Frozen Paddle model changed: {relative}')
    sys.path.insert(0, str(ROOT / 'src'))
    from autovue.result_loader import load_frozen_m25_result
    summary = load_frozen_m25_result(ROOT / 'outputs/M25_final_road_eval').to_dict()['summary']
    expected = json.loads((ROOT / 'tests/regression/m25e_expected.json').read_text())
    keys = ['raw_tracker_ids', 'selected_ocr_crops', 'conservative_clusters',
            'parser_valid_crop_predictions', 'clusters_with_complete_candidate',
            'unique_selected_candidate_strings']
    for key in keys:
        assert summary[key] == expected[key], key
    for status, field in [('VERIFIED_FULL', 'verified_full'), ('CORROBORATED_FRAGMENT', 'corroborated_fragment'),
                          ('NEEDS_REVIEW', 'needs_review'), ('REJECTED', 'rejected')]:
        assert summary[field] == expected['statuses'][status], status
    print('Protected source/model hashes and all ten M25 baseline checks passed.')
    return paddle_cache


def main():
    cache = verify()
    assets = Path(os.environ.get('AUTOVUE_DEPLOY_ASSETS', ROOT / 'app_data/deploy/assets'))
    models = assets / 'models'
    models.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'yolo11n.pt', models / 'yolo11n.pt')
    shutil.copy2(ROOT / 'experiments/detector_benchmark/yolo11n/weights/best.pt', models / 'plate.pt')
    for name in ('PP-OCRv5_server_det', 'PP-OCRv5_server_rec'):
        shutil.copytree(cache / 'official_models' / name,
                        models / 'paddlex/official_models' / name, dirs_exist_ok=True)
    reference = assets / 'reference'
    reference.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'outputs/M25_final_road_eval', reference / 'outputs', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'data/raw/final_road_eval/road_eval.mp4', reference / 'original.mp4')
    for name in ('autovue_result.mp4', 'presentation.mp4'):
        shutil.copy2(ROOT / 'app_data/jobs/m25_reference/video' / name, reference / name)
    if not (ROOT / 'app/frontend/dist/index.html').is_file():
        raise RuntimeError('Build the React frontend before deploying.')
    print(f'Required assets staged at {assets}; originals preserved.')


if __name__ == '__main__':
    main()
