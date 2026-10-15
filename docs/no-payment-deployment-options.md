# AutoVue: local verification and no-payment deployment options

Original assessment: 14 October 2026. Modal GPU deployment is cancelled under the user's explicit no-card, no-billing, no-paid-services constraint. The deployment branch and its implementation remain preserved. On 15 October the user selected free Tailscale Personal Funnel and explicitly granted laptop-owner permission. Authenticated public upload, real GPU inference, results, evidence, and browser video playback passed at https://autovue-review.tail1ab5ad.ts.net. See the [current Tailscale deployment guide](tailscale-deployment.md) for measured limitations and start/stop commands. The options below remain the original feasibility assessment.

## Verified local application

The unchanged recognition pipeline runs on the existing WSL NVIDIA GeForce RTX 4050 Laptop GPU. The execution sandbox hides CUDA devices, but checking and executing in the actual WSL environment confirmed a working GPU. This matters because frozen PaddleOCR uses `gpu:0`; substituting CPU OCR would change the execution requirement.

- All ten existing saved M25 regression checks passed. The regression command wrote its canonical output to a temporary directory, preserving the existing reference result.
- All 27 backend and storage tests passed. Both local Python environments passed `pip check`.
- The React TypeScript/Vite production build passed with the existing Linux Node 22 environment.
- All 16 real local HTTP smoke checks passed. A newly uploaded MP4 ran through GPU tracking, reassociation, PaddleOCR, temporal consensus, canonical result generation, and H.264 rendering. Results, cluster evidence, JPEG crops, and original/presentation/analyzed video ranges were fetched from the API.
- All five real Chromium UI checks passed against the completed live-inference job. Analyze selected the job and played the decoded 768 x 432 presentation video; Results rendered canonical metrics and four candidates; Inspect opened Evidence with five decoded crop images. There were no browser runtime or console errors.
- Protected research source, weight/cache assets, regression expectations, and both original modified detection files retain their recorded SHA-256 hashes.

The representative clip contains 182 frames at 768 x 432 and lasts approximately six seconds. Its real output has 18 raw tracker IDs, 33 selected OCR crops, 18 conservative clusters, six parser-valid predictions, and evidence states of one VERIFIED_FULL, one CORROBORATED_FRAGMENT, two NEEDS_REVIEW, and 14 REJECTED. These are automatic evidence outcomes, not ground-truth accuracy, and they do not replace the full M25 baseline.

The local smoke report and retained job are in ignored runtime storage:

- `app_data/deploy/evidence/local-inference-smoke.json`
- `app_data/deploy/evidence/local-browser-report.json` and `local-{analyze,results,evidence}.png`
- `app_data/deploy/local-verification/jobs/01a4e1f2-cabf-4b40-a169-586955d596fb/`

The test used isolated storage; the pre-existing product jobs and frozen reference artifacts were preserved. There were no simulated inference results and no paid cloud calls.

## Free HTTPS tunnels to the existing GPU laptop

All three tunnel options keep the current React/FastAPI application, both Python environments, model weights, and recognition rules on the laptop. The built React application and API share a single HTTPS origin through the tunnel. Inference and persistent job files stay local. This is the most direct way to keep the complete pipeline while avoiding payment setup. Availability requires the laptop, WSL, FastAPI process, tunnel process, and internet connection to stay running; a stable hostname does not make an offline laptop available.

| Option | Payment/account requirements | Public URL | Review limitations |
| --- | --- | --- | --- |
| Tailscale Funnel | Free Personal account; no billing details needed | Stable device/tailnet HTTPS hostname while names stay unchanged | Funnel is beta with unspecified nonconfigurable bandwidth limits. Large MP4 upload and seeking require public testing. |
| ngrok Free HTTPS | Free account and auth token; use the Free HTTPS plan | Assigned account dev domain; no endpoint session timeout | 1 GB/month outbound transfer and 20,000 requests/month; browser interstitial; usage/credit limits can stop access. |
| Cloudflare Quick Tunnel | No account, payment setup, or purchased domain | Random temporary `trycloudflare.com` hostname | Hostname changes on restart; no uptime guarantee; 200 in-flight requests; 500 MB upload compatibility is unverified. |

Tailscale explicitly states that its Personal plan requires no billing details. Funnel accepts public visitors without requiring them to join the private network, provides HTTPS, and uses the tailnet's DNS domain. Its documented bandwidth limit is not numerically specified. This is the leading candidate when a stable college-review URL and no billing setup are the priority. Use a Personal account rather than enrolling in a business trial. [Personal billing rules](https://tailscale.com/docs/account/billing/modify-billing), [Funnel requirements and limitations](https://tailscale.com/docs/features/tailscale-funnel).

ngrok's Free HTTPS plan includes an assigned dev domain, automatic certificates, and endpoints without a fixed session timeout. Its outbound transfer allowance is 1 GB/month and its request allowance is 20,000/month. Repeated video playback can exhaust outbound transfer; inbound upload should not be conflated with that outbound quota. Visitors see a warning before opening the site, then receive a seven-day suppression cookie. HTTP transport itself documents no request-body size limit, but a five-minute idle timeout applies. Free pricing also lists finite included usage credit; access must not be assumed unlimited or permanently free at any traffic level. Do not upgrade or add a card when limits are reached. [Free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits), [HTTP transport limits](https://ngrok.com/docs/gateway/endpoints/http#limits--timeouts), [current Free pricing](https://ngrok.com/pricing).

Cloudflare Quick Tunnels need no account or domain and produce a temporary public HTTPS URL. Stopping the process ends access, and restarting changes the hostname. AutoVue uses polling, so Quick Tunnel's lack of SSE does not affect current progress updates. Quick Tunnel documentation does not publish a specific upload-size allowance. Cloudflare's general Free proxy table gives a 100 MB upload limit, but that alone does not establish the exact limit of the managed `trycloudflare.com` zone. A real boundary test is necessary before claiming compatibility with AutoVue's unchanged 500 MB upload policy. [Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [general Cloudflare upload limits](https://developers.cloudflare.com/cache/concepts/default-cache-behavior/#upload-limits).

Public tests would still be needed after choosing a tunnel: real upload/inference/progress, authentication and same-origin mutation checks, Results and Evidence navigation, decoded crop images, processed video playback and seeking, and upload-size boundaries. No tunnel has been installed or launched during this assessment.

## Cloud options and exclusions

Lightning AI Free Studios is a finite free-credit cloud-demo candidate. Its current documentation advertises no-card account creation and five initial credits; the extra 25 credits require a card and are excluded. Studios support package installation, ordinary GPUs, persistent environments, public custom ports, and React, so the existing application is technically plausible there. This is an inference from its documented capabilities, not a tested deployment. Credit consumption, account/phone verification, GPU eligibility, cold starts, and public upload/playback limits remain constraints. Only the first 10 GB is documented as unbilled storage; large CUDA environments can exceed it. Credits can be exhausted, and the service attempts workload shutdown when the balance is low. Free-tier limits disagree between pricing and billing documents, so advertised storage caps are not treated as free entitlement. This is not an indefinitely free GPU service, and no account was created or deployment authorized. [Current Studio eligibility and credits](https://api.lightning.ai/docs/platform/build/ai-studio), [public web-app hosting](https://lightning.ai/docs/platform/build/host-web-apps), [storage, credit, and exhaustion rules](https://api.lightning.ai/docs/platform/overview/faq/billing).

Hugging Face's community GPU grants are a conditional cloud route. An educational/research demo using non-PyTorch workloads may be considered for a dedicated GPU grant, which is more plausible for separate PyTorch/Paddle CUDA environments than ZeroGPU. Approval is discretionary. The grant would need to explicitly cover hardware, compute-Space creation permission, its duration, and storage without requiring a payment method. No application or guaranteed grant is claimed. [Official grant guide](https://github.com/huggingface/skills/blob/main/skills/huggingface-spaces/references/grants.md).

Current Hugging Face docs allow eligible free personal accounts with verified email and account age over 30 days to host up to two ZeroGPU Spaces. ZeroGPU is Gradio-only, allocates GPU work through `@spaces.GPU`, and has visitor quotas and queues. Compatibility with AutoVue's separate Paddle environment and CUDA subprocesses is unproven; this is not a drop-in replacement for the existing React/FastAPI worker. Ordinary new Gradio/Docker compute Spaces currently require a paid plan even when CPU Basic hardware has no hourly cost. Static Spaces can serve frontend assets but cannot execute FastAPI/CUDA inference. [ZeroGPU eligibility and compatibility](https://huggingface.co/docs/hub/en/spaces-zerogpu), [current compute-Space creation policy](https://huggingface.co/docs/hub/en/spaces-overview).

Render's Free web hosting can expose a web application over HTTPS, but it supplies no GPU, has small CPU/memory resources and ephemeral filesystem storage, sleeps when idle, and does not offer a free persistent disk. It cannot run the unchanged CUDA PaddleOCR pipeline. A frontend-only deployment with sample outputs would not satisfy live inference. [Free hosting limits](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans).

Google Colab Free is useful for interactive notebook work, but GPU availability is not guaranteed. Its free-runtime policy restricts primarily interacting with a runtime through an external web UI and using distributed workers, and excludes unrelated web hosting. It is not an appropriate permanent React/FastAPI service. [Colab FAQ and allowed-use restrictions](https://research.google.com/colaboratory/faq.html).

## Recommendation before any platform change

Use the existing GPU laptop with a free HTTPS tunnel for an immediate live college demonstration. Tailscale Personal Funnel is the first candidate for a stable hostname and explicit no-billing setup; ngrok Free is an alternative with published outbound quotas; Quick Tunnel is the account-free temporary option. This recommendation preserves the actual inference pipeline. A reliable, indefinitely available, no-card cloud GPU service has not been established. Selecting a platform and publicly exposing the application require the user's next instruction; this report does not authorize that change.
