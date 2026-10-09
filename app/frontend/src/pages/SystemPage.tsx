function SystemPage() {
  return (
    <div className="system-page">

      <header className="route-header">

        <span className="route-eyebrow">
          AutoVue Platform
        </span>

        <h2>
          System Architecture
        </h2>

        <p>
          End-to-end architecture for Indian road-video
          number-plate recognition using detection,
          tracking, OCR and temporal evidence.
        </p>

      </header>


      <section className="panel system-flow-panel">

        <div className="panel-heading">

          <div>
            <h3>
              Recognition Pipeline
            </h3>

            <p>
              From uploaded video to evidence-aware result
            </p>
          </div>

          <span className="reference-badge">
            End-to-End
          </span>

        </div>


        <div className="system-pipeline">

          <article>
            <span>01</span>
            <strong>Video Input</strong>
            <p>
              MP4 road footage uploaded through
              the AutoVue workspace.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>02</span>
            <strong>Vehicle Detection</strong>
            <p>
              YOLO11n locates supported road
              vehicle classes.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>03</span>
            <strong>Tracking</strong>
            <p>
              BoT-SORT assigns temporary track IDs
              across video frames.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>04</span>
            <strong>Plate Localization</strong>
            <p>
              Fine-tuned YOLO11n searches inside
              each vehicle region.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>05</span>
            <strong>OCR</strong>
            <p>
              PaddleOCR with Indian registration
              parsing and rescue strategies.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>06</span>
            <strong>Temporal Consensus</strong>
            <p>
              Multi-frame candidates and fragments
              are consolidated conservatively.
            </p>
          </article>

          <div className="system-arrow">→</div>

          <article>
            <span>07</span>
            <strong>Evidence Result</strong>
            <p>
              Canonical result, video rendering and
              evidence state are exposed through API.
            </p>
          </article>

        </div>

      </section>


      <section className="system-two-column">

        <article className="panel">

          <div className="panel-heading">
            <div>
              <h3>
                Core Model Configuration
              </h3>
              <p>
                Frozen research configuration
              </p>
            </div>
          </div>


          <div className="config-list">

            <div>
              <span>Vehicle detector</span>
              <strong>
                YOLO11n · COCO
              </strong>
            </div>

            <div>
              <span>Vehicle classes</span>
              <strong>
                bicycle · car · motorcycle · bus · truck
              </strong>
            </div>

            <div>
              <span>Vehicle confidence</span>
              <strong>
                0.30
              </strong>
            </div>

            <div>
              <span>Tracker</span>
              <strong>
                BoT-SORT
              </strong>
            </div>

            <div>
              <span>Plate detector</span>
              <strong>
                Fine-tuned YOLO11n
              </strong>
            </div>

            <div>
              <span>Plate confidence</span>
              <strong>
                0.40
              </strong>
            </div>

            <div>
              <span>Plate IoU</span>
              <strong>
                0.70
              </strong>
            </div>

            <div>
              <span>Plate input size</span>
              <strong>
                640 × 640
              </strong>
            </div>

            <div>
              <span>OCR engine</span>
              <strong>
                PaddleOCR
              </strong>
            </div>

            <div>
              <span>Output strategy</span>
              <strong>
                Multi-frame temporal consensus
              </strong>
            </div>

          </div>

        </article>


        <article className="panel">

          <div className="panel-heading">
            <div>
              <h3>
                Application Architecture
              </h3>
              <p>
                Current local product layer
              </p>
            </div>
          </div>


          <div className="architecture-stack">

            <article>
              <div className="architecture-icon">
                UI
              </div>

              <div>
                <strong>
                  React + TypeScript
                </strong>
                <p>
                  Dashboard, upload workspace,
                  results and evidence inspection.
                </p>
              </div>
            </article>

            <article>
              <div className="architecture-icon">
                API
              </div>

              <div>
                <strong>
                  FastAPI
                </strong>
                <p>
                  Job lifecycle, result APIs,
                  media streaming and crop access.
                </p>
              </div>
            </article>

            <article>
              <div className="architecture-icon">
                GPU
              </div>

              <div>
                <strong>
                  Serialized Analysis Worker
                </strong>
                <p>
                  Runs tracking, reassociation,
                  PaddleOCR, consensus and rendering.
                </p>
              </div>
            </article>

            <article>
              <div className="architecture-icon">
                ML
              </div>

              <div>
                <strong>
                  AutoVue Research Pipeline
                </strong>
                <p>
                  Frozen detector, OCR and temporal
                  logic wrapped by regression-safe adapters.
                </p>
              </div>
            </article>

            <article>
              <div className="architecture-icon">
                FS
              </div>

              <div>
                <strong>
                  Local Job Workspace
                </strong>
                <p>
                  Input video, crops, metadata,
                  canonical result and rendered media.
                </p>
              </div>
            </article>

          </div>

        </article>

      </section>


      <section className="panel runtime-panel">

        <div className="panel-heading">

          <div>
            <h3>
              Runtime Environment
            </h3>

            <p>
              Current development workstation
            </p>
          </div>

        </div>


        <div className="runtime-grid">

          <div>
            <span>Operating environment</span>
            <strong>
              Ubuntu 24.04 · WSL2
            </strong>
          </div>

          <div>
            <span>Compute</span>
            <strong>
              NVIDIA RTX 4050 Laptop GPU · 6 GB
            </strong>
          </div>

          <div>
            <span>Primary ML runtime</span>
            <strong>
              Python · PyTorch · Ultralytics
            </strong>
          </div>

          <div>
            <span>OCR runtime</span>
            <strong>
              Separate PaddlePaddle GPU environment
            </strong>
          </div>

          <div>
            <span>Backend</span>
            <strong>
              FastAPI + Uvicorn
            </strong>
          </div>

          <div>
            <span>Frontend</span>
            <strong>
              React + Vite + TypeScript
            </strong>
          </div>

        </div>

      </section>


      <section className="system-two-column">

        <article className="panel">

          <div className="panel-heading">
            <div>
              <h3>
                Product Status
              </h3>
              <p>
                Implemented locally
              </p>
            </div>
          </div>


          <div className="status-checklist">

            <div className="status-complete">
              <span>✓</span>
              Video upload and job creation
            </div>

            <div className="status-complete">
              <span>✓</span>
              GPU analysis worker
            </div>

            <div className="status-complete">
              <span>✓</span>
              Full ANPR inference pipeline
            </div>

            <div className="status-complete">
              <span>✓</span>
              Canonical result generation
            </div>

            <div className="status-complete">
              <span>✓</span>
              Browser-compatible analyzed media
            </div>

            <div className="status-complete">
              <span>✓</span>
              Recognition and evidence UI
            </div>

          </div>

        </article>


        <article className="panel">

          <div className="panel-heading">
            <div>
              <h3>
                Remaining Productization
              </h3>
              <p>
                Planned after the local dashboard
              </p>
            </div>
          </div>


          <div className="status-checklist">

            <div className="status-pending">
              <span>○</span>
              PostgreSQL persistence
            </div>

            <div className="status-pending">
              <span>○</span>
              Human road-video ground truth
            </div>

            <div className="status-pending">
              <span>○</span>
              Final end-to-end metrics
            </div>

            <div className="status-pending">
              <span>○</span>
              Production job queue / recovery
            </div>

            <div className="status-pending">
              <span>○</span>
              AWS deployment
            </div>

            <div className="status-pending">
              <span>○</span>
              Final documentation and demo package
            </div>

          </div>

        </article>

      </section>


      <section className="panel cloud-panel">

        <div className="panel-heading">
          <div>
            <h3>
              Planned Cloud Architecture
            </h3>
            <p>
              Deployment direction — not yet claimed as implemented
            </p>
          </div>
        </div>


        <div className="cloud-flow">

          <div>
            <strong>
              React UI
            </strong>
            <span>
              Browser
            </span>
          </div>

          <b>→</b>

          <div>
            <strong>
              FastAPI
            </strong>
            <span>
              EC2
            </span>
          </div>

          <b>→</b>

          <div>
            <strong>
              GPU Worker
            </strong>
            <span>
              EC2 GPU
            </span>
          </div>

          <b>→</b>

          <div>
            <strong>
              Media
            </strong>
            <span>
              Amazon S3
            </span>
          </div>

          <b>→</b>

          <div>
            <strong>
              Metadata
            </strong>
            <span>
              PostgreSQL / RDS
            </span>
          </div>

        </div>

      </section>


      <footer className="research-footer">
        AutoVue · Indian ANPR Intelligence ·
        Current dashboard represents the local research/product prototype.
      </footer>

    </div>
  );
}


export default SystemPage;
