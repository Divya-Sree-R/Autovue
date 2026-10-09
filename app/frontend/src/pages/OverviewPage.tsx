import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  AutoVueResult,
  ClusterResult,
  EvidenceStatus,
} from "../types/autovue";

import {
  getReferenceResults,
  mediaUrls,
} from "../services/api";



function statusClass(status: EvidenceStatus) {
  return (
    "status " +
    status.toLowerCase().replaceAll("_", "-")
  );
}


function MetricCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function OverviewPage() {
  const [data, setData] =
    useState<AutoVueResult | null>(null);

  const [selectedCluster, setSelectedCluster] =
    useState<ClusterResult | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const originalRef =
    useRef<HTMLVideoElement | null>(null);

  const analyzedRef =
    useRef<HTMLVideoElement | null>(null);


  useEffect(() => {
    getReferenceResults()
      .then((result) => {
        setData(result);

        const preferred =
          result.clusters.find(
            (cluster) =>
              cluster.status === "VERIFIED_FULL"
          ) ??
          result.clusters.find(
            (cluster) =>
              cluster.final_candidate !== null
          ) ??
          result.clusters[0];

        setSelectedCluster(preferred ?? null);
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load AutoVue results."
        );
      });
  }, []);


  function syncAnalyzed() {
    const original = originalRef.current;
    const analyzed = analyzedRef.current;

    if (!original || !analyzed) {
      return;
    }

    const drift = Math.abs(
      original.currentTime -
      analyzed.currentTime
    );

    if (drift > 0.12) {
      analyzed.currentTime =
        original.currentTime;
    }
  }


  function playAnalyzed() {
    const analyzed = analyzedRef.current;

    if (!analyzed) {
      return;
    }

    analyzed.currentTime =
      originalRef.current?.currentTime ?? 0;

    void analyzed.play().catch(() => {
      // Browser playback policies may briefly
      // block programmatic playback.
    });
  }


  function pauseAnalyzed() {
    analyzedRef.current?.pause();
  }


  function seekAnalyzed() {
    const original = originalRef.current;
    const analyzed = analyzedRef.current;

    if (!original || !analyzed) {
      return;
    }

    analyzed.currentTime =
      original.currentTime;
  }


  if (error) {
    return (
      <main className="center-message">
        <h1>AutoVue</h1>
        <p>{error}</p>
        <small>
          Make sure FastAPI is running on port 8000.
        </small>
      </main>
    );
  }


  if (!data) {
    return (
      <main className="center-message">
        <h1>AutoVue</h1>
        <p>Loading road intelligence data...</p>
      </main>
    );
  }


  const summary = data.summary;

  const recognized =
    data.clusters.filter(
      (cluster) =>
        cluster.final_candidate !== null
    );


  return (
    <>

        <header className="topbar">

          <div>
            <h2>Road Video Intelligence</h2>

            <p>
              Vehicle Detection · Plate Localization ·
              Tracking · OCR · Multi-Frame Recognition
            </p>
          </div>

          <div className="api-status">
            <span />
            API Online
          </div>

        </header>


        <section className="metrics">

          <MetricCard
            label="Track Clusters"
            value={summary.conservative_clusters}
          />

          <MetricCard
            label="Complete Candidates"
            value={
              summary
                .clusters_with_complete_candidate
            }
          />

          <MetricCard
            label="Verified"
            value={summary.verified_full}
          />

          <MetricCard
            label="Corroborated"
            value={
              summary.corroborated_fragment
            }
          />

          <MetricCard
            label="Needs Review"
            value={summary.needs_review}
          />

        </section>


        <section className="panel video-panel">

          <div className="panel-heading">

            <div>
              <h3>Video Analysis</h3>
              <p>
                Source footage and AutoVue output
                are synchronized
              </p>
            </div>

            <span className="reference-badge">
              M25 Frozen Reference
            </span>

          </div>


          <div className="video-grid">

            <article className="video-card">

              <div className="video-title">
                <div>
                  <strong>Original Footage</strong>
                  <span>Unmodified road video</span>
                </div>

                <span className="video-dot original-dot" />
              </div>

              <video
                ref={originalRef}
                src={mediaUrls.original}
                controls
                preload="metadata"
                onPlay={playAnalyzed}
                onPause={pauseAnalyzed}
                onSeeked={seekAnalyzed}
                onTimeUpdate={syncAnalyzed}
              />

            </article>


            <article className="video-card">

              <div className="video-title">
                <div>
                  <strong>AutoVue Analysis</strong>
                  <span>
                    Detection + temporal recognition
                  </span>
                </div>

                <span className="video-dot result-dot" />
              </div>

              <video
                ref={analyzedRef}
                src={mediaUrls.presentation}
                muted
                preload="metadata"
              />

            </article>

          </div>


          {selectedCluster && (

            <div className="video-intelligence-strip">

              <div className="video-intelligence-item">

                <span>
                  Selected plate
                </span>

                <strong className="telemetry-plate">
                  {
                    selectedCluster
                      .final_candidate
                    ?? "No candidate"
                  }
                </strong>

              </div>


              <div className="video-intelligence-item">

                <span>
                  Evidence status
                </span>

                <strong>
                  {
                    selectedCluster.status
                      .replaceAll(
                        "_",
                        " "
                      )
                  }
                </strong>

              </div>


              <div className="video-intelligence-item">

                <span>
                  Full-frame support
                </span>

                <strong>
                  {
                    selectedCluster
                      .full_frame_support
                  }
                  {" frames"}
                </strong>

              </div>


              <div className="video-intelligence-item">

                <span>
                  Fragment support
                </span>

                <strong>
                  {
                    selectedCluster
                      .fragment_support_frames
                  }
                  {" frames"}
                </strong>

              </div>


              <div className="video-intelligence-item">

                <span>
                  OCR observations
                </span>

                <strong>
                  {
                    selectedCluster
                      .observations
                      .length
                  }
                </strong>

              </div>

            </div>

          )}

        </section>


        <section className="results-layout">

          <section className="panel results-panel">

            <div className="panel-heading">

              <div>
                <h3>Recognition Results</h3>

                <p>
                  {recognized.length} clusters produced
                  complete plate candidates
                </p>
              </div>

            </div>


            <div className="table-wrapper">

              <table>

                <thead>
                  <tr>
                    <th>Cluster</th>
                    <th>Plate</th>
                    <th>Full</th>
                    <th>Fragment</th>
                    <th>Confidence</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>

                  {recognized.map((cluster) => (

                    <tr
                      key={cluster.cluster_id}
                      className={
                        selectedCluster?.cluster_id ===
                        cluster.cluster_id
                          ? "selected-row"
                          : ""
                      }
                      onClick={() =>
                        setSelectedCluster(cluster)
                      }
                    >

                      <td>
                        #{cluster.cluster_id}
                      </td>

                      <td className="plate-value">
                        {cluster.final_candidate}
                      </td>

                      <td>
                        {cluster.full_frame_support}
                      </td>

                      <td>
                        {
                          cluster
                            .fragment_support_frames
                        }
                      </td>

                      <td>
                        {cluster.mean_confidence !== null
                          ? `${(
                              cluster.mean_confidence *
                              100
                            ).toFixed(1)}%`
                          : "—"}
                      </td>

                      <td>
                        <span
                          className={
                            statusClass(
                              cluster.status
                            )
                          }
                        >
                          {cluster.status}
                        </span>
                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          </section>


          <aside className="panel evidence-panel">

            <div className="panel-heading">

              <div>
                <h3>Evidence Inspector</h3>
                <p>Selected cluster</p>
              </div>

            </div>


            {selectedCluster && (

              <div className="evidence-content">

                <div className="cluster-label">
                  Cluster #{selectedCluster.cluster_id}
                </div>

                <div className="evidence-plate">
                  {selectedCluster.final_candidate ??
                    "No Candidate"}
                </div>


                <span
                  className={
                    statusClass(
                      selectedCluster.status
                    )
                  }
                >
                  {selectedCluster.status}
                </span>


                <div className="evidence-grid">

                  <div>
                    <span>Track IDs</span>
                    <strong>
                      {
                        selectedCluster
                          .member_tracks
                          .join(", ")
                      }
                    </strong>
                  </div>

                  <div>
                    <span>Full Support</span>
                    <strong>
                      {
                        selectedCluster
                          .full_frame_support
                      } frames
                    </strong>
                  </div>

                  <div>
                    <span>Fragment Support</span>
                    <strong>
                      {
                        selectedCluster
                          .fragment_support_frames
                      } frames
                    </strong>
                  </div>

                  <div>
                    <span>Mean Confidence</span>
                    <strong>
                      {
                        selectedCluster
                          .mean_confidence !== null
                          ? `${(
                              selectedCluster
                                .mean_confidence *
                              100
                            ).toFixed(2)}%`
                          : "—"
                      }
                    </strong>
                  </div>

                  <div>
                    <span>OCR Observations</span>
                    <strong>
                      {
                        selectedCluster
                          .observations.length
                      }
                    </strong>
                  </div>

                  <div>
                    <span>Best Fragment</span>
                    <strong>
                      {
                        selectedCluster
                          .best_fragment ??
                        "—"
                      }
                    </strong>
                  </div>

                </div>


                <div className="evidence-explanation">

                  {selectedCluster.status ===
                  "VERIFIED_FULL"
                    ? (
                      <>
                        Repeated complete
                        parser-valid recognition
                        supports this candidate
                        across multiple frames.
                      </>
                    )
                    : selectedCluster.status ===
                      "CORROBORATED_FRAGMENT"
                    ? (
                      <>
                        A complete plate candidate
                        is strengthened by
                        compatible fragment
                        evidence from additional
                        frames.
                      </>
                    )
                    : (
                      <>
                        A complete candidate exists,
                        but the temporal evidence
                        is not strong enough for
                        automatic verification.
                      </>
                    )}

                </div>

              </div>

            )}

          </aside>

        </section>


        <footer>
          AutoVue research prototype · Evidence
          status is not a ground-truth accuracy claim.
        </footer>

    </>
  );
}


export default OverviewPage;
