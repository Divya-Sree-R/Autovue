# AutoVue on free Tailscale Personal Funnel

This deployment keeps the tested React production build, FastAPI API, both Python environments, model weights, and all recognition stages on the existing WSL RTX 4050. Modal remains cancelled and its deployment files/branch are preserved. Tailscale Personal requires no billing details. No card, subscription upgrade, cloud GPU, paid domain, or additional hosted service is needed. [Personal billing policy](https://tailscale.com/docs/account/billing/modify-billing).

The dedicated WSL userspace client proxies one HTTPS hostname to `http://127.0.0.1:8080`. A fresh Windows PowerShell check confirmed an existing running Windows Tailscale service and client binary; they are preserved. The new WSL daemon uses no TUN interface and does not accept DNS, routes, or SSH. WSL loopback hosts the protected demo without changing the existing development API on port 8000 or Vite on 5173. No Windows LAN portproxy, router port forwarding, or `0.0.0.0` app listener is configured. Windows-to-WSL localhost forwarding was verified with a real Windows PowerShell HTTP request to `/health`, returning HTTP 200. [Tailscale WSL guidance](https://tailscale.com/docs/install/windows/wsl2), [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).

Public URL: **https://autovue-review.tail1ab5ad.ts.net**. The laptop owner explicitly approved public access and completed provider-side Funnel enablement on 15 October 2026. Real public upload, GPU inference, results, evidence, browser login, and processed video playback passed. The URL is stable while the node identity, device name, and tailnet name remain unchanged; it only serves the app while the laptop and its processes remain online.

## Final review branch and file audit

The final review branch is `deploy/tailscale-demo`, created from deployment commit `3446233` while preserving `deploy/modal-demo`. This verification run changes only this guide. It reuses the existing FastAPI application, production React build, CUDA environments, model assets, authentication, and approved Funnel configuration; no application rebuild, dependency installation, research experiment, or algorithm change was performed.

The existing Tailscale implementation in `3446233` contains these reviewed deployment files:

| Purpose | Exact files |
| --- | --- |
| Backend public configuration and safeguards | `app/backend/config.py`, `app/backend/main.py`, `app/backend/security.py` |
| Local lifecycle, Funnel, installer, upload diagnostics | `deploy/local_app.py`, `deploy/tailscale_funnel.py`, `deploy/install_tailscale.py`, `deploy/check_upload_limits.py` |
| Deployment checks | `tests/test_local_app_control.py`, `tests/test_funnel_control.py`, `tests/test_public_security.py` |
| Deployment documentation | `docs/tailscale-deployment.md`, `docs/no-payment-deployment-options.md` |

The only original uncommitted work is `src/detection/plate_detection_video.py` and `src/detection/vehicle_detection.py`. Both retain their recorded baseline SHA-256 hashes, respectively `630159d1162f1ff8fef9bde445261d03dd5a9cde092007714c371f4c6e07bdbe` and `c8382c5293d2db04647f81cf932b46748dc3856518ba723e8c5abbfa15142d54`. They are excluded from the deployment commit. Credentials, device keys, generated reports/screenshots, job videos, crops, and model weights remain ignored and are not added to Git.

Fresh verification on 15 October 2026 completed public inference at 23:12 IST using new job `427002f4-d91c-40cf-a322-02dd42d18e76`. All 16 HTTP checks passed: authentication and cross-origin protection, unchanged React routes/assets, invalid-upload cleanup, a real new video upload, progress, RTX 4050 inference with separate PaddleOCR Python, canonical JSON, cluster/crop evidence, and all three video ranges. The worker completed in approximately 50 seconds. All 65 backend/security/controller checks and ten saved M25 baseline checks passed; both Python environments passed dependency checks. Reports are `app_data/funnel/final-public-smoke.json` and `final-public-network.json`.

All eight fresh Chromium checks passed, including the served HTML, JavaScript, and CSS hashes against the existing build, login, actual public relay/TLS, completed-job playback, Results, and all five evidence crops. Its report and screenshots use `app_data/funnel/evidence/final-public-*`. The public relay is explicitly resolved from public DNS to avoid the laptop's private tailnet DNS; certificate verification remains enabled. A separate same-job Analyze `View` check confirmed the existing UI limitation described below; its failed-check proof is `final-public-analyze-view-observation.json`.

A fresh stop/start test also passed: public HTTPS disconnected, port 8080 closed, and the new completed job remained on disk. Startup reused the saved approval and login. Public authentication, the new job's canonical results, and processed-video ranges then passed through TLS-verified relay `103.84.155.153`; see `app_data/funnel/final-restart-smoke.json`. The app and Funnel are left running for review.

## Files and private data

`deploy/local_app.py` safely controls one authenticated loopback FastAPI process. It checks the recorded frozen baseline, existing model/cache assets, both CUDA environments, frontend build assets, and FFmpeg before starting. It sets the project import path explicitly and records the process identity, boot ID, UID, start time, session, and process group to avoid killing unrelated processes or a reused PID.

`deploy/tailscale_funnel.py` controls the dedicated private daemon and the single HTTPS root handler. Login and preparation do not configure Serve or Funnel. After public history exists, they refuse to restart a stopped daemon: use `start`, which checks the authenticated loopback app before a saved background Funnel can resume. `start --owner-approved` records explicit laptop-owner consent for the current node ID, hostname, and port. Future starts reuse that receipt; identity/hostname changes require fresh approval, and changing a saved target port requires reviewing its previous handler first. Stop removes only this Funnel handler; it never resets another user's Tailscale configuration. [Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel).

Runtime files are under ignored `app_data/funnel/`, with a mode-0700 directory and mode-0600 credentials/state/log files:

- `auth.env`: newly generated reviewer username/password. Read this privately; do not commit or paste it into commands, URLs, screenshots, or logs.
- `jobs/`: isolated public-demo uploads, manifests, crops, results, logs, and videos. Existing `app_data/jobs/` workspaces are preserved. Existing frozen reference assets remain read-only inputs.
- `tailscale/`: private device keys, socket, HTTPS certificates, and Tailscale state.
- `app.json`, `tailscaled.json`, `owner-approval.json`, and `public.json`: controller state and consent/configuration records.
- `app.log` and `tailscaled.log`: local diagnostics.

## Exact commands

Run in a normal WSL terminal from the repository root. In the coding-agent sandbox, real GPU, process identity, networking, and thread checks require execution outside that restricted sandbox; regular WSL commands do not. The following installation/login/preparation sequence is for a new setup. This laptop is already configured: use the subsequent `start`/`stop` commands below.

```bash
cd /home/divya/projects/IndianANPR
python3 deploy/install_tailscale.py
python3 deploy/tailscale_funnel.py login
python3 deploy/tailscale_funnel.py prepare
```

The installer downloads only the official Linux AMD64 static package, version 1.104.1, and checks its pinned SHA-256. Both binaries stay inside `app_data/funnel/bin`; no system service is installed. Use a free Personal account for login. A public-email account defaults to Personal; business-domain signup can start a business trial, which is outside this deployment's authorization. [Official package](https://pkgs.tailscale.com/stable/tailscale_1.104.1_amd64.tgz), [account setup](https://tailscale.com/docs/how-to/quickstart).

After the laptop owner explicitly approves public access:

```bash
python3 deploy/tailscale_funnel.py start --owner-approved
```

If Tailscale prints an HTTPS/Funnel enablement URL, the tailnet owner must complete that provider-side approval. It does not require purchasing a plan. Then repeat the start command. Do not run the approval flag unless permission has actually been obtained.

Subsequent starts and status:

```bash
python3 deploy/tailscale_funnel.py start
python3 deploy/tailscale_funnel.py status
```

Stop public access, then the owned app and daemon:

```bash
python3 deploy/tailscale_funnel.py stop
```

For a deliberate restart, wait for running analysis to finish, run `stop`, and run `start` after stop exits successfully. The saved owner receipt, credentials, node identity, uploads, and completed jobs are reused; another authorization flag or login is unnecessary while the existing account session remains valid.

Stop preserves credentials, node identity, uploads, results, and logs. If analysis is active, the public handler is disabled first and the app refuses to terminate until the job completes. Repeat stop after completion. `stop --force` is an explicit emergency action that can interrupt a running analysis; inspect its logs before restarting. Never stop WSL or close/reboot the laptop during a job.

The laptop, WSL, FastAPI process, Tailscale daemon, and internet connection must remain running. Disable sleep manually for the review window if appropriate; this setup does not change Windows power settings or configure automatic startup at boot. Tailscale background Funnel configuration resumes on daemon restart, so use the stop script to disable its handler before stopping the daemon.

## Authentication and abuse limits

Public mode requires an exact expected HTTPS hostname/origin and a random password of at least 24 characters. The generated secret has 32 random bytes. Basic authentication protects the frontend, API, documentation, uploads, analysis requests, evidence images, results, and byte-range video responses. Only a generic health response is anonymous. Share the login only with trusted reviewers: it is one shared demo account with shared access to demo jobs, rather than per-user isolation.

The backend checks Host and mutation Origin headers, rejects cross-site browser mutations, ignores untrusted forwarded client addresses, and returns private/no-store responses. Failed logins are bounded to 20 per minute per transport address with 429 responses; valid credentials still work because Funnel can aggregate visitors behind loopback. This supplements the strong random secret and does not provide distinct per-person lockouts. One upload is accepted at a time; overlapping uploads receive 429. Analysis remains serialized by the existing worker, with 409 for conflicting starts. Avoid running another GPU analysis in the separate development API during a review.

The raw multipart request cap is 504 MiB, allowing normal multipart overhead around the existing **500 MiB file limit** (`500 * 1024 * 1024` bytes). Larger declared/chunked bodies are rejected, with a 60-second upload inactivity timeout and 30-minute total upload receive timeout. Existing empty/corrupt/non-MP4 validation, workspace cleanup, job statuses, canonical JSON, research rules, and file-serving boundaries remain in place.

## Tests and upload limitations

The frozen source/model hashes and ten saved M25 regression checks passed; all 65 backend/security/controller checks passed; the React production build passed; and a new six-second upload completed real local GPU inference through YOLO11n, BoT-SORT, PaddleOCR, reassociation, temporal consensus, and rendering. All 16 local HTTP workflow checks passed, including canonical results, evidence crops, and original/presentation/analyzed video range playback. Both Python environments passed dependency checks. Reports are retained under `app_data/funnel/`.

The public smoke uploaded a new 1,833,354-byte, 182-frame MP4 and completed the actual pipeline in approximately 55 seconds. All 16 public HTTP checks passed, with no transient polling errors. Job `8a17f222-8fc5-4b31-9dfc-336900cb7289` is retained for review. Its automatic output has 18 tracker IDs, 33 OCR crops, 18 clusters, and evidence counts of one verified / one corroborated / two needing review / 14 rejected. This short clip does not replace the full saved M25 regression or establish accuracy against ground truth.

All seven real Chromium public checks passed: HTTP Basic challenge/login, authenticated API access, completed-job Analyze, decoded 768 x 432 presentation video advancing during playback, Results with four candidate rows, Inspect/Evidence with all five crops decoded, and no runtime or console errors. Reports and screenshots are retained in `app_data/funnel/public-smoke.json` and `app_data/funnel/evidence/`.

The real stop script disabled the public handler, disconnected its daemon, and closed port 8080 while preserving jobs and credentials. A fresh `start` reused the saved owner receipt and login, waited for the daemon's transient reconnect state, and restored the same hostname. Post-restart public authentication, retained results, and video ranges passed; both published IPv4 relays returned health HTTP 200 after warmup. See `restart-smoke.json`.

Public testing explicitly used DNS-over-HTTPS results and public relay `103.84.155.153:443`, preserving the original hostname for certificate validation and SNI. Both public IPv4 relays passed TLS and health checks; all four authoritative DNS servers returned public records. The laptop's existing tailnet resolver instead returns its private `100.112.108.110` address, whose HTTPS path timed out during testing. Consequently the API and Chromium tests recorded a public DNS override and actual relay peer, rather than relying on that private path. Outside the tailnet, use the HTTPS URL normally; on the hosting laptop, `http://127.0.0.1:8080` with the same login is also available. No Windows DNS/network settings were changed. See `public-network.json`, `dns-diagnostics.json`, and the browser report for connection evidence.

Initial DNS publication took longer than the documented ten minutes. A single dedicated-node down/up refresh preserved all settings, and public DNS subsequently recovered; the test does not establish what caused that delay. Do not repeatedly reset handlers, rename, or delete the node to address DNS delays.

The real local upload boundary test accepted exactly 524,288,000 bytes (500 MiB) with HTTP 201 and a valid stored-byte range response, then rejected 524,288,001 bytes with HTTP 413 and no orphan workspace. The full 500 MiB public attempt was interrupted before a server response; no successful 500 MiB public transfer is claimed. Practical public upload measurements are recorded separately below.

A valid 16 MiB public upload passed with HTTP 201 in 113.25 seconds, and its stored final-byte range returned HTTP 206. Recovery after the interrupted request also worked. A declared body of 504 MiB + 1 byte returned public HTTP 413 after sending only a bounded 256 KiB prefix, with no new workspace. The proxy may consume a bounded prefix before delivering an early rejection. Reports: `public-upload-16mib.json`, `public-upload-preflight.json`, and `public-upload-boundary-interrupted.json`.

The measured 16 MiB transfer corresponds to approximately 0.14 MiB/s. Extrapolating that one measurement, 500 MiB would take about 59 minutes, exceeding the configured 30-minute upload receive timeout. This is an estimate, not a successful 500 MiB public test or a fixed published Funnel speed. Use small representative clips for college review; the nominal 500 MiB file policy is preserved, while full-size uploads remain unverified over this connection.

An existing Analyze-page limitation was found during final browser review: selecting `View` again for the already-selected completed job clears its recognition preview without retriggering the result-loading effect. The separate Results and Evidence pages, results API, and processed video remain available. Use Results to inspect the completed job, or reload Analyze without reselecting the same job. The frontend source/build is preserved under the explicit no-rebuild requirement; this is a UI limitation, not an inference or tunnel success claim.

Funnel is beta, with nonconfigurable bandwidth limits and no documented numerical upload-size guarantee. Public DNS can take up to ten minutes after first activation; a tailnet resolver may separately return the private Tailscale address. The application accepts up to 500 MiB MP4s, but that does not establish that every network or Funnel path can transfer that amount within the timeouts. Video seeking uses HTTP range requests. [Funnel requirements and limitations](https://tailscale.com/docs/features/tailscale-funnel).

After activation, load credentials into the environment privately and run:

```bash
set -a
source app_data/funnel/auth.env
set +a
.venv/bin/python -B deploy/smoke.py \
  --url https://autovue-review.tail1ab5ad.ts.net \
  --video /tmp/autovue-smoke-road.mp4 --inference \
  --report app_data/funnel/public-smoke.json
.venv/bin/python -B deploy/check_upload_limits.py \
  --url https://autovue-review.tail1ab5ad.ts.net \
  --video /tmp/autovue-smoke-road.mp4 --size-mib 16 \
  --report app_data/funnel/public-upload-16mib.json
```

These commands use the system resolver. If it selects the private tailnet address, run from a public network/resolver or explicitly pin a current public DNS answer for the test while retaining hostname TLS verification; never disable certificate checks. The recorded public API and browser tests used this latter method.

The upload tool sends valid short MP4 footage padded with a standards-compliant `free` box and checks HTTP 201 plus stored-byte range delivery. Its default size is exactly 500 MiB; `--size-mib 16` measures a practical smaller file without changing server policy. `--include-oversize` additionally sends 500 MiB + 1 byte and requires HTTP 413 with no orphan job; this can take a long time over Funnel and is not part of the successful public test. The tool starts no GPU analysis on padded input. Accepted test jobs remain in demo storage; remove them later using the existing authenticated UI/API when no longer needed.
