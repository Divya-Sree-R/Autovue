import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Link,
} from "react-router-dom";

import {
  getJobResults,
  getJobs,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";

import type {
  AutoVueResult,
  EvidenceStatus,
} from "../types/autovue";


type ResultFilter =
  | "CANDIDATES"
  | "ALL"
  | EvidenceStatus;


const FILTERS: ResultFilter[] = [
  "CANDIDATES",
  "ALL",
  "VERIFIED_FULL",
  "CORROBORATED_FRAGMENT",
  "NEEDS_REVIEW",
  "REJECTED",
];


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


function readableStatus(
  status: string
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


function ResultsPage() {

  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [
    selectedJobId,
    setSelectedJobId,
  ] = useState("");

  const [data, setData] =
    useState<AutoVueResult | null>(
      null
    );

  const [search, setSearch] =
    useState("");

  const [filter, setFilter] =
    useState<ResultFilter>(
      "CANDIDATES"
    );

  const [loading, setLoading] =
    useState(true);

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


        if (completed[0]) {
          setSelectedJobId(
            completed[0].job_id
          );
        } else {
          setLoading(false);
        }

      })
      .catch((err) => {

        if (!cancelled) {

          setError(
            err instanceof Error
              ? err.message
              : (
                  "Unable to load "
                  + "analysis jobs."
                )
          );

          setLoading(false);
        }

      });


    return () => {
      cancelled = true;
    };

  }, []);


  useEffect(() => {

    let cancelled = false;


    if (!selectedJobId) {
      return () => {
        cancelled = true;
      };
    }


    getJobResults(
      selectedJobId
    )
      .then((result) => {

        if (!cancelled) {

          setData(
            result
          );

          setError(
            null
          );

          setLoading(
            false
          );
        }

      })
      .catch((err) => {

        if (!cancelled) {

          setData(
            null
          );

          setError(
            err instanceof Error
              ? err.message
              : (
                  "Unable to load "
                  + "recognition results."
                )
          );

          setLoading(
            false
          );
        }

      });


    return () => {
      cancelled = true;
    };

  }, [selectedJobId]);


  const filtered =
    useMemo(() => {

      if (!data) {
        return [];
      }


      const query =
        search
          .trim()
          .toUpperCase();


      return data.clusters.filter(
        (cluster) => {

          let matchesStatus: boolean;

          if (
            filter === "CANDIDATES"
          ) {
            matchesStatus =
              cluster.final_candidate
              !== null;

          } else if (
            filter === "ALL"
          ) {
            matchesStatus = true;

          } else {
            matchesStatus =
              cluster.status
              === filter;
          }


          const plate =
            cluster.final_candidate
            ?? "";


          const matchesSearch =
            query.length === 0
            || plate
              .toUpperCase()
              .includes(query)
            || String(
              cluster.cluster_id
            ).includes(query)
            || cluster.member_tracks
              .join(",")
              .includes(query);


          return (
            matchesStatus
            && matchesSearch
          );

        }
      );

    }, [
      data,
      filter,
      search,
    ]);


  const selectedJob =
    jobs.find(
      (job) =>
        job.job_id
        === selectedJobId
    )
    ?? null;


  function handleJobChange(
    jobId: string
  ) {
    setLoading(
      true
    );

    setData(
      null
    );

    setError(
      null
    );

    setSearch(
      ""
    );

    setFilter(
      "CANDIDATES"
    );

    setSelectedJobId(
      jobId
    );
  }


  return (
    <div className="results-page">

      <header className="route-header results-header">

        <div>

          <span className="route-eyebrow">
            Recognition Intelligence
          </span>

          <h2>
            Recognition Results
          </h2>

          <p>
            Search and inspect plate candidates
            produced from multi-frame AutoVue
            analysis.
          </p>

        </div>


        {jobs.length > 0 && (

          <label className="job-selector">

            <span>
              Analysis job
            </span>

            <select
              value={
                selectedJobId
              }
              onChange={
                (event) =>
                  handleJobChange(
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
                      job.original_filename
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

        )}

      </header>


      {error && (

        <div className="analysis-alert analysis-alert-error">
          {error}
        </div>

      )}


      {!error
        && jobs.length === 0
        && (

          <section className="panel results-empty-state">

            <strong>
              No completed analyses yet
            </strong>

            <span>
              Upload and complete a video
              analysis before viewing results.
            </span>

            <Link
              to="/analyze"
              className="results-link-button"
            >
              Analyze Video
            </Link>

          </section>

        )}


      {loading
        && selectedJobId
        && (

          <section className="panel results-empty-state">

            <strong>
              Loading recognition results…
            </strong>

          </section>

        )}


      {data
        && !loading
        && (

          <>

            <section className="results-summary">

              <div className="result-metric">

                <span>
                  Track Clusters
                </span>

                <strong>
                  {
                    data.summary
                      .conservative_clusters
                  }
                </strong>

              </div>


              <div className="result-metric">

                <span>
                  Plate Candidates
                </span>

                <strong>
                  {
                    data.summary
                      .clusters_with_complete_candidate
                  }
                </strong>

              </div>


              <div className="result-metric result-metric-green">

                <span>
                  Verified
                </span>

                <strong>
                  {
                    data.summary
                      .verified_full
                  }
                </strong>

              </div>


              <div className="result-metric result-metric-blue">

                <span>
                  Corroborated
                </span>

                <strong>
                  {
                    data.summary
                      .corroborated_fragment
                  }
                </strong>

              </div>


              <div className="result-metric result-metric-amber">

                <span>
                  Needs Review
                </span>

                <strong>
                  {
                    data.summary
                      .needs_review
                  }
                </strong>

              </div>

            </section>


            <section className="panel results-browser">

              <div className="results-toolbar">

                <div>

                  <h3>
                    Plate Candidates
                  </h3>

                  <p>
                    {selectedJob
                      ?.original_filename}
                    {" · "}
                    {
                      filtered.length
                    }
                    {" matching clusters"}
                  </p>

                </div>


                <div className="results-search">

                  <span>
                    ⌕
                  </span>

                  <input
                    type="search"
                    placeholder={
                      "Search plate, cluster "
                      + "or track…"
                    }
                    value={
                      search
                    }
                    onChange={
                      (event) =>
                        setSearch(
                          event.target.value
                        )
                    }
                  />

                </div>

              </div>


              <div className="results-filter-row">

                {FILTERS.map(
                  (item) => (

                    <button
                      key={item}
                      type="button"
                      className={
                        filter === item
                          ? (
                              "result-filter "
                              + "result-filter-active"
                            )
                          : "result-filter"
                      }
                      onClick={
                        () =>
                          setFilter(
                            item
                          )
                      }
                    >
                      {item === "CANDIDATES"
                        ? "Recognized"
                        : item === "ALL"
                        ? "All Clusters"
                        : readableStatus(
                            item
                          )}
                    </button>

                  )
                )}

              </div>


              <div className="results-table-wrap">

                <table className="results-table">

                  <thead>

                    <tr>
                      <th>Plate</th>
                      <th>Cluster</th>
                      <th>Tracks</th>
                      <th>Full Support</th>
                      <th>Fragment</th>
                      <th>Confidence</th>
                      <th>Status</th>
                      <th />
                    </tr>

                  </thead>


                  <tbody>

                    {filtered.map(
                      (cluster) => (

                        <tr
                          key={
                            cluster.cluster_id
                          }
                        >

                          <td>

                            <div className="result-plate-cell">

                              <strong>
                                {
                                  cluster
                                    .final_candidate
                                  ?? "No candidate"
                                }
                              </strong>

                              <span>
                                {
                                  cluster
                                    .observations
                                    .length
                                }
                                {" OCR observations"}
                              </span>

                            </div>

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
                            {cluster
                              .mean_confidence
                              !== null
                              ? `${(
                                  cluster
                                    .mean_confidence
                                  * 100
                                ).toFixed(
                                  1
                                )}%`
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
                              {readableStatus(
                                cluster.status
                              )}
                            </span>

                          </td>


                          <td>

                            <Link
                              className="inspect-link"
                              to={
                                `/evidence?job=${
                                  selectedJobId
                                }&cluster=${
                                  cluster.cluster_id
                                }`
                              }
                            >
                              Inspect
                            </Link>

                          </td>

                        </tr>

                      )
                    )}

                  </tbody>

                </table>


                {filtered.length === 0 && (

                  <div className="no-results">
                    No clusters match the
                    current search and filter.
                  </div>

                )}

              </div>

            </section>


            <div className="results-footnote">

              Evidence status reflects temporal
              support strength and is not a
              ground-truth correctness claim.

            </div>

          </>

        )}

    </div>
  );
}


export default ResultsPage;
