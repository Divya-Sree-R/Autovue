# AutoVue on Modal

The deployment branch is `deploy/modal-demo`. The existing React application and FastAPI API share one HTTPS origin. A CPU web function serves the compiled frontend, uploads, manifests, results, crops, and byte-range video playback. It dispatches inference to a separate T4 function with `spawn()`; YOLO11n, BoT-SORT, PaddleOCR, reassociation, temporal consensus, and rendering never run inside the web process. Modal supplies the deployed endpoint; keeping the workspace, application name, and function name stable preserves its URL. No custom domain purchase is required. See [Modal web function URLs](https://modal.com/docs/guide/webhook-urls).

Deployment status: **blocked by Modal billing**. Both images built and both GPU environments passed dependency checks, but Modal rejected deployment with `Please add a payment method to use T4 GPU functions.` No public URL or public inference success is claimed. Local verification passed all ten saved M25 regression checks, 27 backend/storage checks, the TypeScript/Vite build, and an actual HTTP smoke test with a six-second road clip (upload, authentication, validation cleanup, SPA routes, and original-video range playback). Public inference and browser verification remain pending until the workspace has a payment method and metered usage approval.

`deploy/modal_app.py` builds separate web and worker images. The worker keeps PyTorch/CUDA in its main Python environment and PaddleOCR/Paddle GPU in `/opt/paddle`; their dependencies and NumPy versions remain separate. The deployment copies the exact existing vehicle/plate weights and cached PP-OCRv5 detector/recognizer assets. It does not retrain, replace model weights, or change inference thresholds. Requirements are pinned in `deploy/requirements-{web,main,paddle}.txt`.

`deploy/prepare.py` verifies `deploy/baseline.json` before staging assets into ignored `app_data/deploy/assets`. This checks the saved M25 expectations, protected research sources, model assets, regression expectations, and both user-modified detection files against their pre-deployment SHA-256 snapshots. Original artifacts are preserved. The frozen baseline commit is `e098f7ccec54207b6b606c843574c7dbfecec8dd`; saved-output expectations are 45 tracker IDs, 92 OCR crops, 43 clusters, 15 parser-valid crop predictions, eight clusters with complete candidates, six unique candidate strings, and evidence counts 2 verified / 2 corroborated / 4 needs review / 35 rejected. These checks validate saved outputs, not rerun inference.

The persistent `autovue-demo-data` Volume is mounted at `/data` in both functions. Uploaded MP4s, job manifests, canonical results, logs, crops, metadata, and rendered videos live under `/data/jobs`. Read-only reference assets are copied into the web image; model assets are copied into the worker image. `deploy/runtime.py` reloads the Volume before API requests and commits successful mutations before returning success. Worker manifest updates commit progress and artifacts. Dispatch and worker receipts are separate files so the web process cannot overwrite a running worker's manifest. API requests are serialized to avoid reloading the Volume while an upload or video response holds an open file. These explicit synchronization operations follow [Modal Volume semantics](https://modal.com/docs/guide/volumes).

The configured settings are:

| Setting | Deployment value or purpose |
| --- | --- |
| `AUTOVUE_MODAL_APP` | `autovue-demo`; keep stable for redeployment |
| `AUTOVUE_MODAL_VOLUME` | `autovue-demo-data`; keep stable to retain jobs |
| `AUTOVUE_MODAL_AUTH_SECRET` | `autovue-demo-auth` |
| `AUTOVUE_DEPLOY_ASSETS` | Local staging directory; defaults to `app_data/deploy/assets` |
| `AUTOVUE_PADDLE_CACHE` | Existing local Paddle cache for preparation; defaults to `~/.paddlex` |
| `AUTOVUE_JOBS_ROOT` | `/data/jobs`; local default remains `app_data/jobs` |
| `AUTOVUE_FRONTEND_DIST` | `/opt/autovue/frontend`; unset locally retains API-only root JSON |
| `AUTOVUE_CORS_ORIGINS` | Empty in production; local default permits Vite development origins |
| `AUTOVUE_REQUIRE_AUTH` | `1` in the web function; missing credentials prevent startup |
| `AUTOVUE_AUTH_USERNAME`, `AUTOVUE_AUTH_PASSWORD` | Injected only into the web function from the Modal Secret |
| `AUTOVUE_MAIN_PYTHON` | `/usr/local/bin/python`; local default remains `.venv/bin/python` |
| `AUTOVUE_PADDLE_PYTHON` | `/opt/paddle/bin/python`; local default remains `.venv_paddleocr/bin/python` |
| `AUTOVUE_VEHICLE_MODEL_PATH`, `AUTOVUE_PLATE_MODEL_PATH` | Packaged exact vehicle and plate weights |
| `AUTOVUE_FROZEN_OUTPUT_ROOT`, `AUTOVUE_REFERENCE_*` | Packaged reference result, original/tracking/analyzed/presentation videos, and crops |
| `VITE_API_BASE` | Optional frontend API override; production defaults to the current origin |

Browser Basic authentication covers the frontend, API, documentation, evidence images, and video requests; only `GET /health` is public. Credential comparisons use constant-time digest comparison. The HTTPS Modal endpoint is the intended access path. Browser mutations require the same origin; cross-site mutations are rejected. Uploads retain the existing MP4-only, 500 MB policy and readable-frame validation. Job IDs, workspace boundaries, crop filenames, and served files are checked for traversal and symlinks. SPA fallback does not convert unknown API routes into HTML. Credentials are excluded from image source and Git; local `.modal.toml` and `.env.modal` are ignored and mode `0600`. See [Modal Secrets](https://modal.com/docs/guide/secrets).

The public API endpoints, job statuses, canonical result structure, evidence states, and local worker behavior remain unchanged. Pipeline exceptions become `FAILED` jobs. Worker timeout/termination is reconciled on subsequent API requests using Modal call receipts. An interrupted dispatch without a durable receipt becomes `FAILED` after 70 minutes. There is no automatic inference retry or duplicate rerun of completed jobs.

To recreate an isolated deployment CLI when the existing `/tmp/autovue-modal-tools/bin/modal` is unavailable:

```bash
python3 -m venv app_data/deploy/cli
app_data/deploy/cli/bin/python -m pip install modal==1.6.1
export MODAL_CONFIG_PATH="$PWD/.modal.toml"
app_data/deploy/cli/bin/modal token new
```

Existing authenticated sessions can reuse the ignored `.modal.toml`; do not commit or display its contents. The `autovue-demo-auth` Secret must contain both authentication environment variables. The initial deployment already created this Secret. Rotate it through the Modal dashboard when needed; do not put credentials in deployment source or shell command arguments.

From the repository root, rebuild, verify/stage, test, and redeploy:

```bash
export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"
npm --prefix app/frontend run build
.venv/bin/python -B deploy/prepare.py
PYTHONPATH=src:. .venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'
export MODAL_CONFIG_PATH="$PWD/.modal.toml"
app_data/deploy/cli/bin/modal deploy deploy/modal_app.py
```

The CLI used during initial deployment was `/tmp/autovue-modal-tools/bin/modal` version `1.6.1`; substitute that path while it remains available. Keep copied source directories unchanged during a build, because changing an uploaded file can invalidate its checksum. Redeploying retains the named Volume and existing jobs. The deployment requires existing ignored model/reference assets and a built React frontend; a fresh Git clone alone does not contain those large files.

For local HTTP checks against the production frontend layout, start the existing backend in a separate terminal:

```bash
AUTOVUE_FRONTEND_DIST="$PWD/app/frontend/dist" PYTHONPATH=src:. \
  .venv/bin/python -B -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

Then use `deploy/smoke.py --url http://127.0.0.1:8000 --video PATH_TO_SMALL_MP4 --report /tmp/autovue-local-smoke.json`. For complete public verification, export the credentials from the ignored local secret file and supply the actual deployment URL:

```bash
set -a
source .env.modal
set +a
.venv/bin/python -B deploy/smoke.py \
  --url https://ACTUAL_DEPLOYMENT_URL.modal.run \
  --video PATH_TO_SMALL_REPRESENTATIVE_MP4 \
  --inference --report /tmp/autovue-public-smoke.json
```

The smoke runner checks authentication, CSRF rejection, React routes/assets, invalid upload cleanup, upload persistence, original-video ranges, independent inference, progress, canonical results/summary, cluster evidence, JPEG crops, and processed-video ranges. It retains the uploaded job for review and records failures as well as successes. Polling defaults to a two-hour deadline so a cold worker/image startup is not confused with a quick inference failure. Backend checks cover authentication, environment configuration, path protection, static route isolation, dispatch, synchronization, and worker reconciliation. In this WSL agent sandbox, Starlette TestClient's thread wakeups require running the same tests outside the sandbox; that is an execution-environment restriction, not an application dependency change.

Both functions use `min_containers=0` and `max_containers=1`. The T4 worker requests two CPU cores and 8192 MiB RAM, has a one-hour execution timeout, no retries, and a 30-second idle window. The web function requests one CPU core and 2048 MiB RAM, has a 600-second timeout, and a 60-second idle window. Neither reserves an always-running container. Requests after scale-down may pay a cold-start delay. See [Modal autoscaling](https://modal.com/docs/guide/scale).

As checked on 14 October 2026, Modal lists T4 compute at **$0.000164/second**, approximately **$0.59/GPU-hour**, plus CPU and memory usage. Load time and the configured idle window are billable; compute charging stops after scale-down to zero. Volume storage is listed at **$0.09/GiB/month**, with up to **1 TiB included free**; network egress and plan credits also affect the bill. No paid plan, domain, or service purchase is required by this configuration. Actual charges depend on the workspace plan and usage. See [Modal pricing](https://modal.com/pricing).

Known demo limits are shared Basic credentials and shared job visibility; one inference job at a time; cold starts; a one-hour worker limit; no automatic retries; and serialization of complete web responses, so a slow upload or long video stream can delay other API requests. Jobs have no automatic retention period; use the existing UI/API deletion after analysis finishes. The 500 MB validation policy is preserved, but large transfers remain subject to network speed and Modal's web request limits. Costs stop for compute when idle, while retained storage remains persistent.

The existing frontend lint check reports one effect-state error and one missing-effect-dependency warning in unchanged `AnalyzePage.tsx`. The production build passes. Frozen OCR requires CUDA, so local upload/API testing does not substitute for the public T4 inference test.
