"""Deploy with: modal deploy deploy/modal_app.py

Ships the existing inference code and exact local model assets. Nothing under
M01–M25 is rewritten. A CPU web function serves the SPA/API; one independent
T4 worker processes jobs. Both functions have zero minimum warm containers.
"""
import os
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = '/opt/autovue'
APP_NAME = os.environ.get('AUTOVUE_MODAL_APP', 'autovue-demo')
VOLUME_NAME = os.environ.get('AUTOVUE_MODAL_VOLUME', 'autovue-demo-data')
AUTH_SECRET = os.environ.get('AUTOVUE_MODAL_AUTH_SECRET', 'autovue-demo-auth')
ASSETS = Path(os.environ.get('AUTOVUE_DEPLOY_ASSETS', ROOT / 'app_data/deploy/assets'))
app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

environment = {
    'PYTHONPATH': f'{REMOTE_ROOT}/src:{REMOTE_ROOT}',
    'AUTOVUE_JOBS_ROOT': '/data/jobs',
    'YOLO_CONFIG_DIR': '/tmp/ultralytics',
    'PYTHONUNBUFFERED': '1',
}

web_image = (
    modal.Image.debian_slim(python_version='3.12')
    .pip_install_from_requirements(str(ROOT / 'deploy/requirements-web.txt'))
    .env(environment)
    .add_local_dir(str(ROOT / 'app/backend'), f'{REMOTE_ROOT}/app/backend', copy=True)
    .add_local_file(str(ROOT / 'app/__init__.py'), f'{REMOTE_ROOT}/app/__init__.py', copy=True)
    .add_local_dir(str(ROOT / 'src/autovue'), f'{REMOTE_ROOT}/src/autovue', copy=True)
    .add_local_dir(str(ROOT / 'deploy'), f'{REMOTE_ROOT}/deploy', copy=True)
    .add_local_dir(str(ROOT / 'app/frontend/dist'), f'{REMOTE_ROOT}/frontend', copy=True)
    .add_local_dir(str(ASSETS / 'reference'), f'{REMOTE_ROOT}/reference', copy=True)
)

worker_image = (
    modal.Image.debian_slim(python_version='3.12')
    .apt_install('ffmpeg', 'libgl1', 'libglib2.0-0')
    .pip_install('torch==2.14.1+cu126', 'torchvision==0.29.1+cu126',
                 index_url='https://download.pytorch.org/whl/cu126')
    .pip_install_from_requirements(str(ROOT / 'deploy/requirements-main.txt'))
    .pip_install('fastapi==0.143.0', 'pydantic==2.13.5')
    .add_local_file(str(ROOT / 'deploy/requirements-paddle.txt'), '/tmp/requirements-paddle.txt', copy=True)
    .run_commands(
        'python -m venv /opt/paddle',
        '/opt/paddle/bin/pip install paddlepaddle-gpu==3.2.1 --index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/',
        '/opt/paddle/bin/pip install -r /tmp/requirements-paddle.txt',
        'python -m pip check', '/opt/paddle/bin/python -m pip check',
    )
    .env({**environment,
          'AUTOVUE_MAIN_PYTHON': '/usr/local/bin/python',
          'AUTOVUE_PADDLE_PYTHON': '/opt/paddle/bin/python',
          'AUTOVUE_VEHICLE_MODEL_PATH': f'{REMOTE_ROOT}/assets/yolo11n.pt',
          'AUTOVUE_PLATE_MODEL_PATH': f'{REMOTE_ROOT}/assets/plate.pt',
          'PADDLE_PDX_CACHE_HOME': f'{REMOTE_ROOT}/assets/paddlex',
          'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True'})
    .add_local_dir(str(ROOT / 'src'), f'{REMOTE_ROOT}/src', copy=True)
    .add_local_dir(str(ROOT / 'app/backend'), f'{REMOTE_ROOT}/app/backend', copy=True)
    .add_local_file(str(ROOT / 'app/__init__.py'), f'{REMOTE_ROOT}/app/__init__.py', copy=True)
    .add_local_dir(str(ASSETS / 'models'), f'{REMOTE_ROOT}/assets', copy=True)
    .run_commands(f'mkdir -p {REMOTE_ROOT}/experiments/detector_benchmark/yolo11n/weights',
                  f'ln -s {REMOTE_ROOT}/assets/plate.pt {REMOTE_ROOT}/experiments/detector_benchmark/yolo11n/weights/best.pt')
)


@app.function(image=worker_image, gpu='T4', cpu=2, memory=8192,
              volumes={'/data': volume}, timeout=3600, retries=0,
              min_containers=0, max_containers=1, scaledown_window=30)
def analyze(job_id: str):
    import json
    from app.backend.services import runtime
    from app.backend.services.jobs import job_input_path, load_job
    from app.backend.worker.analysis import _run_pipeline

    volume.reload()
    if load_job(job_id)['status'] != 'QUEUED':
        return  # Duplicate delivery cannot rerun or overwrite a finished job.
    receipt = job_input_path(job_id).parents[1] / 'worker_call.json'
    receipt.write_text(json.dumps({'call_id': modal.current_function_call_id()}))
    volume.commit()
    runtime.commit_storage = volume.commit
    os.chdir(REMOTE_ROOT)
    _run_pipeline(job_id)
    volume.commit()
    return load_job(job_id)['status']


@app.function(
    image=web_image, cpu=1, memory=2048, volumes={'/data': volume},
    secrets=[modal.Secret.from_name(AUTH_SECRET, required_keys=[
        'AUTOVUE_AUTH_USERNAME', 'AUTOVUE_AUTH_PASSWORD'])],
    env={
        'AUTOVUE_REQUIRE_AUTH': '1', 'AUTOVUE_CORS_ORIGINS': '',
        'AUTOVUE_FRONTEND_DIST': f'{REMOTE_ROOT}/frontend',
        'AUTOVUE_FROZEN_OUTPUT_ROOT': f'{REMOTE_ROOT}/reference/outputs',
        'AUTOVUE_REFERENCE_ORIGINAL_VIDEO': f'{REMOTE_ROOT}/reference/original.mp4',
        'AUTOVUE_REFERENCE_CROP_DIR': f'{REMOTE_ROOT}/reference/outputs/M25B_tracking/best_plate_crops',
        'AUTOVUE_REFERENCE_TRACKING_VIDEO': f'{REMOTE_ROOT}/reference/outputs/M25B_tracking/tracking_best_plate.mp4',
        'AUTOVUE_REFERENCE_ANALYZED_VIDEO': f'{REMOTE_ROOT}/reference/autovue_result.mp4',
        'AUTOVUE_REFERENCE_PRESENTATION_VIDEO': f'{REMOTE_ROOT}/reference/presentation.mp4',
    },
    min_containers=0, max_containers=1, scaledown_window=60, timeout=600,
)
@modal.concurrent(max_inputs=1)
@modal.asgi_app()
def web():
    from app.backend.main import app as application
    from deploy.runtime import attach

    return attach(application, volume=volume, worker=analyze,
                  call_factory=modal.FunctionCall.from_id)
