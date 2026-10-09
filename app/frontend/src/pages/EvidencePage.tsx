import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useSearchParams,
} from "react-router-dom";

import {
  getJobResults,
  getJobs,
  jobCropUrl,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";

import type {
  AutoVueResult,
  ClusterResult,
  EvidenceStatus,
} from "../types/autovue";


function statusClass(
  status: EvidenceStatus
) {
  return (
    "status "
    + status
      .toLowerCase()
      .replaceAll(
        "_",
        "-"
      )
  );
}


function humanStatus(
  status: EvidenceStatus
) {
  return status
    .replaceAll(
      "_",
      " "
    );
}


function percent(
  value: number | null
) {
  if (
    value === null
    || Number.isNaN(value)
  ) {
    return "—";
  }

  return (
    `${(
      value * 100
    ).toFixed(1)}%`
  );
}


function statusExplanation(
  cluster: ClusterResult
) {
  switch (
    cluster.status
  ) {
    case "VERIFIED_FULL":
      return (
        "The complete parser-valid plate candidate "
        + "was supported repeatedly across multiple "
        + "frames. AutoVue therefore assigns its "
        + "strongest temporal evidence state."
      );

    case "CORROBORATED_FRAGMENT":
      return (
        "A complete plate candidate exists and is "
        + "strengthened by compatible partial OCR "
        + "evidence observed in additional frames."
      );

    case "NEEDS_REVIEW":
      return (
        "A complete plate candidate exists, but the "
        + "available temporal evidence is not strong "
        + "enough for automatic verification. Human "
        + "review is recommended."
      );

    case "REJECTED":
      return (
        "The cluster did not produce sufficient "
        + "parser-valid temporal evidence for a "
        + "complete plate candidate."
      );
  }
}


function EvidencePage() {

  const [
    searchParams,
    setSearchParams,
  ] = useSearchParams();

  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [jobId, setJobId] =
    useState(
      searchParams.get(
        "job"
      ) ?? ""
    );

  const [data, setData] =
    useState<AutoVueResult | null>(
      null
    );

  const [
    selectedClusterId,
    setSelectedClusterId,
  ] = useState<number | null>(
    (() => {
      const value =
        searchParams.get(
          "cluster"
        );

      return value
        ? Number(value)
        : null;
    })()
  );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(
      null
    );


  useEffect(() => {

    getJobs()
      .then(
        (items) => {

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
            !jobId
            && completed.length > 0
          ) {
            setJobId(
              completed[0]
                .job_id
            );
          }

        }
      )
      .catch(
        (err) => {

          setError(
            err instanceof Error
              ? err.message
              : (
                  "Could not load "
                  + "analysis jobs."
                )
          );

          setLoading(
            false
          );

        }
      );

  }, [jobId]);


  useEffect(() => {

    if (!jobId) {
      return;
    }

    let cancelled = false;


    getJobResults(
      jobId
    )
      .then(
        (result) => {

          if (cancelled) {
            return;
          }

          setData(
            result
          );

          setError(
            null
          );


          setSelectedClusterId(
            (
              currentClusterId
            ) => {

              const requested =
                currentClusterId
                  !== null
                  ? result.clusters.find(
                      (cluster) =>
                        cluster.cluster_id
                        === currentClusterId
                    )
                  : null;


              const preferred =
                requested
                ?? result.clusters.find(
                  (cluster) =>
                    cluster.status
                    === "VERIFIED_FULL"
                )
                ?? result.clusters.find(
                  (cluster) =>
                    cluster.final_candidate
                    !== null
                )
                ?? result.clusters[0];


              return (
                preferred
                  ?.cluster_id
                ?? null
              );
            }
          );

          setLoading(
            false
          );

        }
      )
      .catch(
        (err) => {

          if (cancelled) {
            return;
          }

          setError(
            err instanceof Error
              ? err.message
              : (
                  "Could not load "
                  + "evidence."
                )
          );

          setLoading(
            false
          );

        }
      );


    return () => {
      cancelled = true;
    };

  }, [jobId]);


  const selectedCluster =
    useMemo(
      () => {

        if (
          !data
          || selectedClusterId
            === null
        ) {
          return null;
        }

        return (
          data.clusters.find(
            (cluster) =>
              cluster.cluster_id
              === selectedClusterId
          )
          ?? null
        );

      },
      [
        data,
        selectedClusterId,
      ]
    );


  const candidateClusters =
    useMemo(
      () => {

        if (!data) {
          return [];
        }

        return [
          ...data.clusters,
        ].sort(
          (a, b) => {

            const aHas =
              a.final_candidate
              !== null;

            const bHas =
              b.final_candidate
              !== null;

            if (
              aHas !== bHas
            ) {
              return aHas
                ? -1
                : 1;
            }

            return (
              a.cluster_id
              - b.cluster_id
            );
          }
        );

      },
      [data]
    );


  function chooseCluster(
    clusterId: number
  ) {

    setSelectedClusterId(
      clusterId
    );

    setSearchParams({
      job: jobId,
      cluster:
        String(
          clusterId
        ),
    });
  }


  function chooseJob(
    newJobId: string
  ) {

    setLoading(
      true
    );

    setData(
      null
    );

    setSelectedClusterId(
      null
    );

    setJobId(
      newJobId
    );

    setSearchParams({
      job: newJobId,
    });
  }


  if (
    loading
    && !data
  ) {
    return (
      <main className="center-message">
        <h1>Evidence Review</h1>
        <p>
          Loading AutoVue evidence…
        </p>
      </main>
    );
  }


  return (
    <div className="evidence-page">

      <header className="route-header evidence-route-header">

        <div>

          <span className="route-eyebrow">
            Evidence Intelligence
          </span>

          <h2>
            Evidence Review
          </h2>

          <p>
            Inspect the observations and
            temporal evidence behind each
            AutoVue recognition result.
          </p>

        </div>


        <label className="job-selector">

          <span>
            Analysis Job
          </span>

          <select
            value={jobId}
            onChange={
              (event) =>
                chooseJob(
                  event.target.value
                )
            }
          >

            {jobs.map(
              (job) => (

                <option
                  key={job.job_id}
                  value={job.job_id}
                >
                  {job.original_filename}
                  {" · "}
                  {job.job_id.slice(
                    0,
                    8
                  )}
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


      {data && selectedCluster && (

        <>

          <section className="evidence-hero panel">

            <div className="evidence-hero-main">

              <div>

                <span className="evidence-kicker">
                  Selected recognition
                </span>

                <div className="evidence-main-plate">
                  {
                    selectedCluster
                      .final_candidate
                    ?? "NO CANDIDATE"
                  }
                </div>

                <div className="evidence-identity">

                  <span
                    className={
                      statusClass(
                        selectedCluster
                          .status
                      )
                    }
                  >
                    {humanStatus(
                      selectedCluster
                        .status
                    )}
                  </span>

                  <span>
                    Cluster #
                    {
                      selectedCluster
                        .cluster_id
                    }
                  </span>

                  <span>
                    Track
                    {
                      selectedCluster
                        .member_tracks
                        .length > 1
                        ? "s "
                        : " "
                    }

                    {
                      selectedCluster
                        .member_tracks
                        .join(", ")
                    }
                  </span>

                </div>

              </div>


              <label className="cluster-selector">

                <span>
                  Inspect Cluster
                </span>

                <select
                  value={
                    selectedCluster
                      .cluster_id
                  }
                  onChange={
                    (event) =>
                      chooseCluster(
                        Number(
                          event.target
                            .value
                        )
                      )
                  }
                >

                  {candidateClusters.map(
                    (cluster) => (

                      <option
                        key={
                          cluster
                            .cluster_id
                        }
                        value={
                          cluster
                            .cluster_id
                        }
                      >
                        #{cluster.cluster_id}
                        {" · "}
                        {
                          cluster
                            .final_candidate
                          ?? "No candidate"
                        }
                        {" · "}
                        {humanStatus(
                          cluster.status
                        )}
                      </option>

                    )
                  )}

                </select>

              </label>

            </div>


            <div className="evidence-metrics">

              <div>
                <span>
                  Full support
                </span>
                <strong>
                  {
                    selectedCluster
                      .full_frame_support
                  }
                  {" "}
                  frames
                </strong>
              </div>

              <div>
                <span>
                  Fragment support
                </span>
                <strong>
                  {
                    selectedCluster
                      .fragment_support_frames
                  }
                  {" "}
                  frames
                </strong>
              </div>

              <div>
                <span>
                  Mean confidence
                </span>
                <strong>
                  {percent(
                    selectedCluster
                      .mean_confidence
                  )}
                </strong>
              </div>

              <div>
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

              <div>
                <span>
                  Best fragment
                </span>
                <strong>
                  {
                    selectedCluster
                      .best_fragment
                    ?? "—"
                  }
                </strong>
              </div>

            </div>


            <div className="evidence-reason">

              <strong>
                Why this status?
              </strong>

              <p>
                {statusExplanation(
                  selectedCluster
                )}
              </p>

              <small>
                Evidence status describes
                temporal support strength.
                It is not a ground-truth
                correctness claim.
              </small>

            </div>

          </section>


          <section className="panel evidence-observations-panel">

            <div className="panel-heading">

              <div>
                <h3>
                  Plate Observations
                </h3>

                <p>
                  Frame-level crops selected
                  for OCR and temporal analysis
                </p>
              </div>

              <span className="reference-badge">
                {
                  selectedCluster
                    .observations.length
                }
                {" "}
                observations
              </span>

            </div>


            {selectedCluster
              .observations.length === 0
              ? (

                <div className="evidence-empty">
                  No OCR observations were
                  retained for this cluster.
                </div>

              )
              : (

                <div className="observation-grid">

                  {selectedCluster
                    .observations
                    .map(
                      (
                        observation,
                        index
                      ) => (

                        <article
                          className="observation-card"
                          key={
                            observation
                              .filename
                          }
                        >

                          <div className="crop-frame">

                            <img
                              src={
                                jobCropUrl(
                                  jobId,
                                  observation
                                    .filename
                                )
                              }
                              alt={
                                `Plate crop from frame ${
                                  observation.frame
                                }`
                              }
                              loading="lazy"
                            />

                          </div>


                          <div className="observation-body">

                            <div className="observation-heading">

                              <strong>
                                Observation #
                                {index + 1}
                              </strong>

                              <span>
                                Frame {
                                  observation
                                    .frame
                                }
                              </span>

                            </div>


                            <dl>

                              <div>
                                <dt>
                                  Raw OCR
                                </dt>
                                <dd>
                                  {
                                    observation
                                      .final_raw
                                    ?? observation
                                      .raw_0deg
                                    ?? "—"
                                  }
                                </dd>
                              </div>

                              <div>
                                <dt>
                                  Final OCR
                                </dt>
                                <dd className="plate-value">
                                  {
                                    observation
                                      .final_prediction
                                    ?? "—"
                                  }
                                </dd>
                              </div>

                              <div>
                                <dt>
                                  OCR confidence
                                </dt>
                                <dd>
                                  {percent(
                                    observation
                                      .final_confidence
                                  )}
                                </dd>
                              </div>

                              <div>
                                <dt>
                                  Plate detector
                                </dt>
                                <dd>
                                  {percent(
                                    observation
                                      .plate_confidence
                                  )}
                                </dd>
                              </div>

                              <div>
                                <dt>
                                  Quality
                                </dt>
                                <dd>
                                  {
                                    observation
                                      .quality_score
                                      .toFixed(3)
                                  }
                                </dd>
                              </div>

                              <div>
                                <dt>
                                  Track
                                </dt>
                                <dd>
                                  #
                                  {
                                    observation
                                      .track_id
                                  }
                                </dd>
                              </div>

                            </dl>


                            <div className="observation-flags">

                              {observation
                                .orientation_triggered
                                && (
                                  <span>
                                    Orientation rescue
                                    {
                                      observation
                                        .selected_rotation
                                        !== null
                                        ? ` · ${
                                            observation
                                              .selected_rotation
                                          }°`
                                        : ""
                                    }
                                  </span>
                                )}

                              {observation
                                .preprocessing_triggered
                                && (
                                  <span>
                                    Preprocessing
                                    {
                                      observation
                                        .selected_variant
                                        ? ` · ${
                                            observation
                                              .selected_variant
                                          }`
                                        : ""
                                    }
                                  </span>
                                )}

                              {observation
                                .final_valid_plate
                                && (
                                  <span className="valid-observation">
                                    Parser valid
                                  </span>
                                )}

                            </div>

                          </div>

                        </article>

                      )
                    )}

                </div>

              )}

          </section>


          <section className="evidence-detail-grid">

            <section className="panel">

              <div className="panel-heading">

                <div>
                  <h3>
                    Candidate Options
                  </h3>
                  <p>
                    Complete parser-valid
                    candidates considered
                  </p>
                </div>

              </div>


              {selectedCluster
                .candidate_options
                .length === 0
                ? (

                  <div className="evidence-empty">
                    No complete candidate
                    options were produced.
                  </div>

                )
                : (

                  <div className="evidence-table-wrap">

                    <table>

                      <thead>
                        <tr>
                          <th>
                            Candidate
                          </th>
                          <th>
                            Frames
                          </th>
                          <th>
                            Tracks
                          </th>
                          <th>
                            Confidence
                          </th>
                          <th>
                            Selected
                          </th>
                        </tr>
                      </thead>

                      <tbody>

                        {selectedCluster
                          .candidate_options
                          .map(
                            (candidate) => (

                              <tr
                                key={
                                  candidate
                                    .plate
                                }
                              >

                                <td className="plate-value">
                                  {
                                    candidate
                                      .plate
                                  }
                                </td>

                                <td>
                                  {
                                    candidate
                                      .frame_support
                                  }
                                </td>

                                <td>
                                  {
                                    candidate
                                      .track_support
                                  }
                                </td>

                                <td>
                                  {percent(
                                    candidate
                                      .mean_confidence
                                  )}
                                </td>

                                <td>
                                  {
                                    candidate
                                      .selected
                                      ? "Yes"
                                      : "No"
                                  }
                                </td>

                              </tr>

                            )
                          )}

                      </tbody>

                    </table>

                  </div>

                )}

            </section>


            <section className="panel">

              <div className="panel-heading">

                <div>
                  <h3>
                    Fragment Corroboration
                  </h3>

                  <p>
                    Partial OCR evidence
                    compatible with the
                    selected candidate
                  </p>

                </div>

              </div>


              {selectedCluster
                .fragment_evidence
                .length === 0
                ? (

                  <div className="evidence-empty">
                    No corroborating fragments
                    were used for this cluster.
                  </div>

                )
                : (

                  <div className="fragment-list">

                    {selectedCluster
                      .fragment_evidence
                      .map(
                        (
                          fragment,
                          index
                        ) => (

                          <article
                            key={
                              `${fragment.support_frame}-${index}`
                            }
                          >

                            <div>
                              <strong className="plate-value">
                                {
                                  fragment
                                    .matching_fragment
                                }
                              </strong>

                              <span>
                                Raw: {
                                  fragment
                                    .raw_text
                                }
                              </span>
                            </div>


                            <div>
                              <span>
                                Frame {
                                  fragment
                                    .support_frame
                                }
                              </span>

                              <span>
                                Track #
                                {
                                  fragment
                                    .original_track_id
                                }
                              </span>
                            </div>

                          </article>

                        )
                      )}

                  </div>

                )}

            </section>

          </section>

        </>

      )}

    </div>
  );
}


export default EvidencePage;
