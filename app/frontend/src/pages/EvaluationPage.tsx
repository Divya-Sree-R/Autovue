import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getJobResults,
  getJobs,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";

import type {
  AutoVueResult,
  ClusterResult,
  EvidenceStatus,
} from "../types/autovue";


function percentage(
  value: number,
  total: number
) {
  if (total <= 0) {
    return 0;
  }

  return (
    value / total
  ) * 100;
}


function formatPercent(
  value: number
) {
  return `${value.toFixed(1)}%`;
}


function statusLabel(
  status: EvidenceStatus
) {
  return status
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(
      /\b\w/g,
      (letter) =>
        letter.toUpperCase()
    );
}


function statusClass(
  status: EvidenceStatus
) {
  return (
    "status " +
    status
      .toLowerCase()
      .replaceAll("_", "-")
  );
}


function candidatePriority(
  cluster: ClusterResult
) {
  const statusOrder:
    Record<EvidenceStatus, number> = {
      VERIFIED_FULL: 0,
      CORROBORATED_FRAGMENT: 1,
      NEEDS_REVIEW: 2,
      REJECTED: 3,
    };

  return statusOrder[
    cluster.status
  ];
}


function EvaluationPage() {
  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [
    selectedJobId,
    setSelectedJobId,
  ] = useState<string | null>(
    null
  );

  const [
    loadedJobId,
    setLoadedJobId,
  ] = useState<string | null>(
    null
  );

  const [data, setData] =
    useState<AutoVueResult | null>(
      null
    );

  const [error, setError] =
    useState<string | null>(
      null
    );


  useEffect(() => {
    let cancelled = false;

    getJobs()
      .then((items) => {
        if (cancelled) {
          return;
        }

        const completed =
          items.filter(
            (job) =>
              job.status
              === "COMPLETED"
          );

        setJobs(
          completed
        );

        if (
          completed.length > 0
        ) {
          setSelectedJobId(
            completed[0].job_id
          );
        }
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : (
                "Could not load "
                + "analysis jobs."
              )
        );
      });

    return () => {
      cancelled = true;
    };
  }, []);


  useEffect(() => {
    if (!selectedJobId) {
      return;
    }

    let cancelled = false;

    getJobResults(
      selectedJobId
    )
      .then((result) => {
        if (cancelled) {
          return;
        }

        setData(result);
        setLoadedJobId(
          selectedJobId
        );
        setError(null);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : (
                "Could not load "
                + "analysis results."
              )
        );
      });

    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);


  const selectedJob =
    useMemo(
      () =>
        jobs.find(
          (job) =>
            job.job_id
            === selectedJobId
        ) ?? null,
      [
        jobs,
        selectedJobId,
      ]
    );


  const candidates =
    useMemo(() => {
      if (!data) {
        return [];
      }

      return data.clusters
        .filter(
          (cluster) =>
            cluster.final_candidate
            !== null
        )
        .sort(
          (a, b) => {
            const priority =
              candidatePriority(a)
              - candidatePriority(b);

            if (priority !== 0) {
              return priority;
            }

            return (
              (b.mean_confidence ?? 0)
              -
              (a.mean_confidence ?? 0)
            );
          }
        );
    }, [data]);


  const summary =
    data?.summary ?? null;


  const candidateCount =
    summary
      ?.clusters_with_complete_candidate
    ?? 0;


  const clusterCount =
    summary
      ?.conservative_clusters
    ?? 0;


  const strongEvidence =
    (
      summary?.verified_full
      ?? 0
    )
    +
    (
      summary
        ?.corroborated_fragment
      ?? 0
    );


  const reviewCount =
    summary?.needs_review
    ?? 0;


  const rejectedCount =
    summary?.rejected
    ?? 0;


  const meanConfidence =
    candidates.length > 0
      ? (
          candidates.reduce(
            (
              total,
              cluster
            ) =>
              total
              +
              (
                cluster
                  .mean_confidence
                ?? 0
              ),
            0
          )
          /
          candidates.length
        )
        * 100
      : 0;


  const totalObservations =
    data
      ? data.clusters.reduce(
          (
            total,
            cluster
          ) =>
            total
            +
            cluster
              .observations
              .length,
          0
        )
      : 0;


  const breakdown = [
    {
      label:
        "Verified Full",
      count:
        summary?.verified_full
        ?? 0,
      className:
        "analytics-bar-verified",
    },
    {
      label:
        "Corroborated",
      count:
        summary
          ?.corroborated_fragment
        ?? 0,
      className:
        "analytics-bar-corroborated",
    },
    {
      label:
        "Needs Review",
      count:
        reviewCount,
      className:
        "analytics-bar-review",
    },
    {
      label:
        "Rejected",
      count:
        rejectedCount,
      className:
        "analytics-bar-rejected",
    },
  ];


  function changeJob(
    jobId: string
  ) {
    setSelectedJobId(
      jobId
    );

    setLoadedJobId(
      null
    );

    setData(
      null
    );

    setError(
      null
    );
  }


  if (
    jobs.length === 0
    && !error
  ) {
    return (
      <div className="analytics-page">

        <header className="route-header">

          <span className="route-eyebrow">
            AutoVue Intelligence
          </span>

          <h2>
            Analytics
          </h2>

          <p>
            Operational insights from
            completed road-video analyses.
          </p>

        </header>


        <section className="panel dashboard-empty-state">

          <div className="empty-state-icon">
            ◉
          </div>

          <h3>
            No completed analyses yet
          </h3>

          <p>
            Run a road video from the
            Analyze page. Its recognition
            analytics will appear here.
          </p>

        </section>

      </div>
    );
  }


  return (
    <div className="analytics-page">

      <header className="route-header analytics-header">

        <div>

          <span className="route-eyebrow">
            Recognition Intelligence
          </span>

          <h2>
            Analytics
          </h2>

          <p>
            Understand recognition coverage,
            evidence strength and review
            requirements for an AutoVue run.
          </p>

        </div>


        <label className="dashboard-selector">

          <span>
            Analysis
          </span>

          <select
            value={
              selectedJobId
              ?? ""
            }
            onChange={
              (event) =>
                changeJob(
                  event.target.value
                )
            }
          >
            {jobs.map(
              (job) => (
                <option
                  key={
                    job.job_id
                  }
                  value={
                    job.job_id
                  }
                >
                  {
                    job
                      .original_filename
                  }
                  {" · "}
                  {
                    job.job_id.slice(
                      0,
                      8
                    )
                  }
                </option>
              )
            )}
          </select>

        </label>

      </header>


      {error && (
        <div className="analysis-alert analysis-alert-error">
          {error}
        </div>
      )}


      {(
        !data
        ||
        loadedJobId
        !== selectedJobId
      ) ? (

        <section className="panel dashboard-loading">
          Loading AutoVue analytics…
        </section>

      ) : (

        <>

          <section className="analytics-kpi-grid">

            <article className="analytics-kpi">

              <span>
                Track clusters
              </span>

              <strong>
                {clusterCount}
              </strong>

              <small>
                Conservative vehicle
                clusters
              </small>

            </article>


            <article className="analytics-kpi analytics-kpi-blue">

              <span>
                Plate candidates
              </span>

              <strong>
                {candidateCount}
              </strong>

              <small>
                Complete registration
                candidates
              </small>

            </article>


            <article className="analytics-kpi analytics-kpi-green">

              <span>
                Strong evidence
              </span>

              <strong>
                {strongEvidence}
              </strong>

              <small>
                Verified +
                corroborated
              </small>

            </article>


            <article className="analytics-kpi analytics-kpi-amber">

              <span>
                Needs review
              </span>

              <strong>
                {reviewCount}
              </strong>

              <small>
                Candidate clusters
                requiring inspection
              </small>

            </article>

          </section>


          <section className="analytics-main-grid">

            <article className="panel analytics-overview-panel">

              <div className="panel-heading">

                <div>
                  <h3>
                    Recognition Coverage
                  </h3>

                  <p>
                    How temporal evidence
                    resolved tracked clusters
                  </p>
                </div>


                <span className="reference-badge">
                  {
                    selectedJob
                      ?.original_filename
                    ?? "Completed run"
                  }
                </span>

              </div>


              <div className="analytics-score-grid">

                <div className="analytics-score">

                  <span>
                    Candidate coverage
                  </span>

                  <strong>
                    {
                      formatPercent(
                        percentage(
                          candidateCount,
                          clusterCount
                        )
                      )
                    }
                  </strong>

                  <small>
                    complete candidates /
                    clusters
                  </small>

                </div>


                <div className="analytics-score">

                  <span>
                    Strong-evidence share
                  </span>

                  <strong>
                    {
                      formatPercent(
                        percentage(
                          strongEvidence,
                          candidateCount
                        )
                      )
                    }
                  </strong>

                  <small>
                    among complete
                    candidates
                  </small>

                </div>


                <div className="analytics-score">

                  <span>
                    Review share
                  </span>

                  <strong>
                    {
                      formatPercent(
                        percentage(
                          reviewCount,
                          candidateCount
                        )
                      )
                    }
                  </strong>

                  <small>
                    candidates requiring
                    manual review
                  </small>

                </div>


                <div className="analytics-score">

                  <span>
                    Mean candidate confidence
                  </span>

                  <strong>
                    {
                      formatPercent(
                        meanConfidence
                      )
                    }
                  </strong>

                  <small>
                    recognized candidates
                  </small>

                </div>

              </div>


              <div className="analytics-breakdown">

                <div className="analytics-section-title">

                  <div>
                    <strong>
                      Evidence distribution
                    </strong>

                    <span>
                      {clusterCount}
                      {" "}
                      total clusters
                    </span>
                  </div>

                </div>


                <div className="analytics-stacked-bar">

                  {breakdown.map(
                    (item) => (
                      <span
                        key={
                          item.label
                        }
                        className={
                          item
                            .className
                        }
                        style={{
                          width:
                            `${percentage(
                              item.count,
                              clusterCount
                            )}%`,
                        }}
                        title={
                          `${item.label}: `
                          + item.count
                        }
                      />
                    )
                  )}

                </div>


                <div className="analytics-legend">

                  {breakdown.map(
                    (item) => (
                      <div
                        key={
                          item.label
                        }
                      >

                        <span
                          className={
                            `analytics-legend-dot `
                            + item
                              .className
                          }
                        />

                        <span>
                          {item.label}
                        </span>

                        <strong>
                          {item.count}
                        </strong>

                      </div>
                    )
                  )}

                </div>

              </div>

            </article>


            <aside className="panel analytics-signal-panel">

              <div className="panel-heading">

                <div>
                  <h3>
                    Run Signals
                  </h3>

                  <p>
                    Useful operational
                    indicators
                  </p>
                </div>

              </div>


              <div className="signal-list">

                <div className="signal-item">

                  <span>
                    OCR observations
                  </span>

                  <strong>
                    {totalObservations}
                  </strong>

                </div>


                <div className="signal-item">

                  <span>
                    Selected crops
                  </span>

                  <strong>
                    {
                      summary
                        ?.selected_ocr_crops
                      ?? 0
                    }
                  </strong>

                </div>


                <div className="signal-item">

                  <span>
                    Parser-valid crops
                  </span>

                  <strong>
                    {
                      summary
                        ?.parser_valid_crop_predictions
                      ?? 0
                    }
                  </strong>

                </div>


                <div className="signal-item">

                  <span>
                    Unique selected strings
                  </span>

                  <strong>
                    {
                      summary
                        ?.unique_selected_candidate_strings
                      ?? 0
                    }
                  </strong>

                </div>

              </div>


              <div className="analytics-note">

                <strong>
                  Evidence-aware output
                </strong>

                <p>
                  Verified, corroborated and
                  review states describe the
                  strength of temporal
                  recognition evidence. They
                  are not ground-truth
                  correctness labels.
                </p>

              </div>

            </aside>

          </section>


          <section className="panel analytics-candidates-panel">

            <div className="panel-heading">

              <div>

                <h3>
                  Recognized Candidates
                </h3>

                <p>
                  Highest-value recognition
                  results from this analysis
                </p>

              </div>


              <span className="reference-badge">
                {candidates.length}
                {" candidates"}
              </span>

            </div>


            {candidates.length === 0 ? (

              <div className="dashboard-empty-inline">
                No complete plate candidates
                were produced.
              </div>

            ) : (

              <div className="table-wrapper">

                <table className="analytics-table">

                  <thead>

                    <tr>
                      <th>Plate</th>
                      <th>Cluster</th>
                      <th>Tracks</th>
                      <th>Full Support</th>
                      <th>Fragment</th>
                      <th>Confidence</th>
                      <th>Status</th>
                    </tr>

                  </thead>


                  <tbody>

                    {candidates.map(
                      (cluster) => (

                        <tr
                          key={
                            cluster
                              .cluster_id
                          }
                        >

                          <td className="plate-value">
                            {
                              cluster
                                .final_candidate
                            }
                          </td>

                          <td>
                            #
                            {
                              cluster
                                .cluster_id
                            }
                          </td>

                          <td>
                            {
                              cluster
                                .member_tracks
                                .join(", ")
                            }
                          </td>

                          <td>
                            {
                              cluster
                                .full_frame_support
                            }
                          </td>

                          <td>
                            {
                              cluster
                                .fragment_support_frames
                            }
                          </td>

                          <td>
                            {
                              cluster
                                .mean_confidence
                              !== null
                                ? `${(
                                    cluster
                                      .mean_confidence
                                    * 100
                                  ).toFixed(
                                    1
                                  )}%`
                                : "—"
                            }
                          </td>

                          <td>

                            <span
                              className={
                                statusClass(
                                  cluster
                                    .status
                                )
                              }
                            >
                              {
                                statusLabel(
                                  cluster
                                    .status
                                )
                              }
                            </span>

                          </td>

                        </tr>

                      )
                    )}

                  </tbody>

                </table>

              </div>

            )}

          </section>

        </>

      )}

    </div>
  );
}


export default EvaluationPage;
