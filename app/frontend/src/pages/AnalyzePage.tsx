import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  deleteJob,
  getJobResults,
  getJobs,
  jobMediaUrls,
  runJob,
  uploadVideo,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";

import type {
  AutoVueResult,
} from "../types/autovue";


const RUNNING_STATUSES = new Set([
  "QUEUED",
  "DETECTING_TRACKING",
  "OCR_PROCESSING",
  "TEMPORAL_CONSENSUS",
  "RENDERING",
]);


const PIPELINE_STAGES = [
  {
    status: "UPLOADED",
    label: "Video uploaded",
    description:
      "Input video stored in the AutoVue job workspace.",
  },
  {
    status: "QUEUED",
    label: "Queued",
    description:
      "Waiting for the serialized analysis worker.",
  },
  {
    status: "DETECTING_TRACKING",
    label: "Detection & tracking",
    description:
      "Vehicle detection, BoT-SORT tracking and plate crop selection.",
  },
  {
    status: "OCR_PROCESSING",
    label: "OCR processing",
    description:
      "PaddleOCR, Indian plate parsing and rescue strategies.",
  },
  {
    status: "TEMPORAL_CONSENSUS",
    label: "Temporal consensus",
    description:
      "Multi-frame candidate voting and fragment corroboration.",
  },
  {
    status: "RENDERING",
    label: "Building output",
    description:
      "Canonical result generation and analyzed video rendering.",
  },
  {
    status: "COMPLETED",
    label: "Completed",
    description:
      "Results and media are ready for review.",
  },
];


function formatBytes(
  bytes: number
) {
  if (bytes === 0) {
    return "0 B";
  }

  const units = [
    "B",
    "KB",
    "MB",
    "GB",
  ];

  const exponent = Math.min(
    Math.floor(
      Math.log(bytes) /
      Math.log(1024)
    ),
    units.length - 1
  );

  const value =
    bytes /
    Math.pow(
      1024,
      exponent
    );

  return (
    `${value.toFixed(
      exponent === 0 ? 0 : 1
    )} ${units[exponent]}`
  );
}


function humanStage(
  status: string
) {
  return status.replaceAll(
    "_",
    " "
  );
}


function statusClass(
  status: string
) {
  return (
    "status " +
    status
      .toLowerCase()
      .replaceAll(
        "_",
        "-"
      )
  );
}


function pipelineStepClass(
  job: AnalysisJob | null,
  index: number
) {
  if (!job) {
    return "pipeline-step";
  }

  if (
    job.status === "COMPLETED"
  ) {
    return (
      "pipeline-step " +
      "pipeline-step-complete"
    );
  }

  const activeIndex =
    PIPELINE_STAGES.findIndex(
      (stage) =>
        stage.status ===
        job.status
    );

  if (
    activeIndex === -1
  ) {
    return "pipeline-step";
  }

  if (index < activeIndex) {
    return (
      "pipeline-step " +
      "pipeline-step-complete"
    );
  }

  if (index === activeIndex) {
    return (
      "pipeline-step " +
      "pipeline-step-active"
    );
  }

  return "pipeline-step";
}


function AnalyzePage() {

  const [file, setFile] =
    useState<File | null>(
      null
    );

  const [jobs, setJobs] =
    useState<AnalysisJob[]>(
      []
    );

  const [
    selectedJob,
    setSelectedJob,
  ] = useState<AnalysisJob | null>(
    null
  );

  const [
    results,
    setResults,
  ] = useState<AutoVueResult | null>(
    null
  );

  const [resultsLoading, setResultsLoading] =
    useState(false);


  const [uploading, setUploading] =
    useState(false);

  const [
    startingJobId,
    setStartingJobId,
  ] = useState<string | null>(
    null
  );

  const [error, setError] =
    useState<string | null>(
      null
    );

  const [
    resultError,
    setResultError,
  ] = useState<string | null>(
    null
  );


  const previewUrl = useMemo(
    () => (
      file
        ? URL.createObjectURL(
            file
          )
        : null
    ),
    [file]
  );


  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(
          previewUrl
        );
      }
    };
  }, [previewUrl]);


  // -------------------------------------------------------
  // Poll job manifests
  // -------------------------------------------------------

  useEffect(() => {

    let cancelled = false;


    async function refreshJobs() {

      try {

        const latest =
          await getJobs();

        if (cancelled) {
          return;
        }


        setJobs(
          latest
        );


        setSelectedJob(
          (current) => {

            const runningJob =
              latest.find(
                (item) =>
                  RUNNING_STATUSES.has(
                    item.status
                  )
              );

            const completedJob =
              latest.find(
                (item) =>
                  item.status
                  === "COMPLETED"
              );


            if (!current) {
              return (
                runningJob
                ?? completedJob
                ?? latest[0]
                ?? null
              );
            }


            return (
              latest.find(
                (item) =>
                  item.job_id ===
                  current.job_id
              )
              ?? runningJob
              ?? completedJob
              ?? latest[0]
              ?? null
            );
          }
        );

      } catch {
        // Keep page usable during
        // temporary backend/network issues.
      }
    }


    void refreshJobs();


    const timer =
      window.setInterval(
        () => {
          void refreshJobs();
        },
        1000
      );


    return () => {

      cancelled = true;

      window.clearInterval(
        timer
      );
    };

  }, []);


  // -------------------------------------------------------
  // Load canonical results after completion
  // Retry briefly because COMPLETED status and the result
  // request can become visible to the UI almost together.
  // -------------------------------------------------------

  useEffect(() => {

    let cancelled = false;

    let retryTimer:
      number | null = null;

    let attempts = 0;


    if (
      selectedJob?.status
      !== "COMPLETED"
    ) {

      setResultsLoading(
        false
      );

      return () => {
        cancelled = true;
      };
    }


    async function loadResults() {

      if (
        cancelled
        || !selectedJob
      ) {
        return;
      }


      setResultsLoading(
        true
      );


      try {

        const data =
          await getJobResults(
            selectedJob.job_id
          );


        if (cancelled) {
          return;
        }


        setResults(
          data
        );

        setResultError(
          null
        );

        setResultsLoading(
          false
        );

      } catch (err) {

        if (cancelled) {
          return;
        }


        attempts += 1;


        // Avoid showing an error during a normal
        // short hand-off from worker completion
        // to canonical-result availability.
        if (attempts >= 5) {

          setResultError(
            err instanceof Error
              ? err.message
              : (
                  "Unable to load "
                  + "analysis results."
                )
          );

          setResultsLoading(
            false
          );

          return;
        }


        retryTimer =
          window.setTimeout(
            () => {
              void loadResults();
            },
            1000
          );
      }
    }


    void loadResults();


    return () => {

      cancelled = true;

      if (
        retryTimer !== null
      ) {

        window.clearTimeout(
          retryTimer
        );
      }
    };

  }, [
    selectedJob?.job_id,
    selectedJob?.status,
  ]);


  const activeJob =
    jobs.find(
      (job) =>
        RUNNING_STATUSES.has(
          job.status
        )
    )
    ?? null;


  const selectedMedia =
    selectedJob
      ? jobMediaUrls(
          selectedJob.job_id
        )
      : null;


  const sourceVideo =
    previewUrl
    ?? selectedMedia?.original
    ?? null;


  const recognized =
    results?.clusters.filter(
      (cluster) =>
        cluster.final_candidate
        !== null
    )
    ?? [];



  const recognitionPlaceholder = (() => {

    if (
      selectedJob?.status
      === "COMPLETED"
    ) {

      return {
        title:
          resultsLoading
            ? "Loading recognition results"
            : "Preparing recognition results",

        message:
          "Analysis is complete. AutoVue is loading "
          + "the canonical plate evidence.",
      };
    }


    if (
      selectedJob
      && RUNNING_STATUSES.has(
        selectedJob.status
      )
    ) {

      return {
        title:
          "Analysis in progress",

        message:
          selectedJob.message
          || (
            "AutoVue is processing the "
            + "uploaded road video."
          ),
      };
    }


    if (
      selectedJob?.status
      === "UPLOADED"
    ) {

      return {
        title:
          "Ready to analyze",

        message:
          "Start analysis to detect vehicles, "
          + "localize plates and build "
          + "temporal recognition evidence.",
      };
    }


    return {
      title:
        "Waiting for video",

      message:
        "Upload or select an analysis job "
        + "to view recognition results.",
    };
  })();


  const primaryResult =
    recognized.find(
      (cluster) =>
        cluster.status
        === "VERIFIED_FULL"
    )
    ?? recognized[0]
    ?? null;


  function handleFile(
    selected: File | null
  ) {

    setError(null);

    setResultError(null);


    if (!selected) {

      setFile(null);

      return;
    }


    if (
      !selected.name
        .toLowerCase()
        .endsWith(".mp4")
    ) {

      setFile(null);

      setError(
        "AutoVue currently accepts MP4 videos only."
      );

      return;
    }


    setFile(
      selected
    );

    setSelectedJob(
      null
    );

    setResults(
      null
    );
  }


  async function handleUpload() {

    if (
      !file
      || uploading
    ) {
      return;
    }


    setUploading(
      true
    );

    setError(
      null
    );


    try {

      const job =
        await uploadVideo(
          file
        );


      setJobs(
        (previous) => [
          job,
          ...previous.filter(
            (item) =>
              item.job_id !==
              job.job_id
          ),
        ]
      );


      setResults(
        null
      );

      setResultError(
        null
      );

      setSelectedJob(
        job
      );

      setFile(
        null
      );

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : "Video upload failed."
      );

    } finally {

      setUploading(
        false
      );

    }
  }


  async function handleRun(
    jobId: string
  ) {

    if (
      startingJobId
      !== null
    ) {
      return;
    }


    setStartingJobId(
      jobId
    );

    setError(
      null
    );


    try {

      const job =
        await runJob(
          jobId
        );


      setJobs(
        (previous) =>
          previous.map(
            (item) =>
              item.job_id
              === job.job_id
                ? job
                : item
          )
      );


      setResults(
        null
      );

      setResultError(
        null
      );

      setSelectedJob(
        job
      );

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : (
              "Could not start "
              + "AutoVue analysis."
            )
      );

    } finally {

      setStartingJobId(
        null
      );

    }
  }


  async function handleDelete(
    job: AnalysisJob
  ) {

    if (
      RUNNING_STATUSES.has(
        job.status
      )
    ) {
      setError(
        "A job cannot be deleted while AutoVue is processing it."
      );

      return;
    }


    const confirmed =
      window.confirm(
        `Delete "${job.original_filename}"?\n\n`
        + "This permanently removes the uploaded video, "
        + "plate crops, metadata, recognition results "
        + "and generated analysis videos for this job."
      );


    if (!confirmed) {
      return;
    }


    setError(
      null
    );


    try {

      await deleteJob(
        job.job_id
      );


      setJobs(
        (previous) =>
          previous.filter(
            (item) =>
              item.job_id
              !== job.job_id
          )
      );


      if (
        selectedJob?.job_id
        === job.job_id
      ) {

        setSelectedJob(
          null
        );

        setResults(
          null
        );

        setResultError(
          null
        );

        setFile(
          null
        );
      }

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : "Could not delete analysis job."
      );

    }
  }


  function selectExistingJob(
    job: AnalysisJob
  ) {

    setFile(
      null
    );

    setError(
      null
    );

    setResultError(
      null
    );

    setResults(
      null
    );

    setSelectedJob(
      job
    );
  }


  function jobAction(
    job: AnalysisJob
  ) {

    const running =
      RUNNING_STATUSES.has(
        job.status
      );


    const workerBusy =
      activeJob !== null
      && activeJob.job_id
        !== job.job_id;


    let primaryAction;


    if (
      job.status
      === "UPLOADED"
    ) {

      primaryAction = (
        <button
          type="button"
          className="table-action"
          disabled={
            startingJobId
            === job.job_id
            || workerBusy
          }
          title={
            workerBusy
              ? "Another AutoVue job is currently running."
              : "Run AutoVue analysis"
          }
          onClick={() =>
            void handleRun(
              job.job_id
            )
          }
        >
          {startingJobId
            === job.job_id
              ? "Starting..."
              : workerBusy
              ? "Worker Busy"
              : "Run"}
        </button>
      );

    } else {

      primaryAction = (
        <button
          type="button"
          className="table-action"
          onClick={() =>
            selectExistingJob(
              job
            )
          }
        >
          {job.status
            === "COMPLETED"
              ? "View"
              : "Open"}
        </button>
      );
    }


    return (
      <div className="job-table-actions">

        {primaryAction}


        {!running && (

          <button
            type="button"
            className="
              table-action
              table-action-danger
            "
            title={
              "Delete this analysis job "
              + "and all of its stored files"
            }
            onClick={() =>
              void handleDelete(
                job
              )
            }
          >
            Delete
          </button>

        )}

      </div>
    );
  }


  return (
    <div className="analyze-page">

      <header className="route-header analyze-header">

        <span className="route-eyebrow">
          AutoVue Workspace
        </span>

        <h2>
          Analyze Road Video
        </h2>

        <p>
          Upload road footage, run the complete
          Indian ANPR pipeline, and inspect the
          resulting temporal recognition evidence.
        </p>

      </header>


      {error && (

        <div className="analysis-alert analysis-alert-error">
          {error}
        </div>

      )}


      {activeJob
        && selectedJob
        && activeJob.job_id
          !== selectedJob.job_id
        && (

          <div className="analysis-alert analysis-alert-info">

            <div>
              <strong>
                AutoVue is processing another video
              </strong>

              <span>
                {activeJob.original_filename}
                {" · "}
                {humanStage(activeJob.status)}
                {" · "}
                {activeJob.progress}%
              </span>
            </div>

            <button
              type="button"
              className="table-action"
              onClick={() =>
                selectExistingJob(
                  activeJob
                )
              }
            >
              Open Running Job
            </button>

          </div>

        )}


      <section className="analysis-workspace-grid">

        <article className="panel source-workspace">

          <div className="panel-heading">

            <div>
              <h3>Source Video</h3>

              <p>
                Upload and preview footage before
                starting analysis
              </p>
            </div>


            {selectedJob && (

              <span className="workspace-badge">
                {humanStage(
                  selectedJob.status
                )}
              </span>

            )}

          </div>


          <div className="source-workspace-body">

            {sourceVideo ? (

              <div className="source-video-frame">

                <video
                  key={sourceVideo}
                  src={sourceVideo}
                  controls
                  preload="metadata"
                />

              </div>

            ) : (

              <label className="source-empty-state">

                <input
                  type="file"
                  accept="video/mp4,.mp4"
                  onChange={
                    (event) =>
                      handleFile(
                        event.target
                          .files?.[0]
                        ?? null
                      )
                  }
                />

                <div className="source-upload-icon">
                  ↑
                </div>

                <strong>
                  Upload a road video
                </strong>

                <span>
                  Select an MP4 file to preview
                  and test with AutoVue
                </span>

              </label>

            )}


            <div className="source-controls">

              <div className="source-meta">

                {file ? (
                  <>
                    <strong>
                      {file.name}
                    </strong>

                    <span>
                      {formatBytes(
                        file.size
                      )}
                      {" · Local preview"}
                    </span>
                  </>
                ) : selectedJob ? (
                  <>
                    <strong>
                      {
                        selectedJob
                          .original_filename
                      }
                    </strong>

                    <span>
                      {formatBytes(
                        selectedJob
                          .size_bytes
                      )}
                      {" · Job "}
                      {
                        selectedJob
                          .job_id
                          .slice(
                            0,
                            8
                          )
                      }
                    </span>
                  </>
                ) : (
                  <>
                    <strong>
                      No video selected
                    </strong>

                    <span>
                      MP4 · maximum 500 MB
                    </span>
                  </>
                )}

              </div>


              <div className="source-actions">

                <label className="secondary-button analyze-file-button">

                  {sourceVideo
                    ? "Choose Another"
                    : "Choose Video"}

                  <input
                    type="file"
                    accept="video/mp4,.mp4"
                    onChange={
                      (event) =>
                        handleFile(
                          event.target
                            .files?.[0]
                          ?? null
                        )
                    }
                  />

                </label>


                {file && (

                  <button
                    type="button"
                    className="primary-button compact-primary"
                    disabled={
                      uploading
                    }
                    onClick={
                      () =>
                        void handleUpload()
                    }
                  >
                    {uploading
                      ? "Uploading..."
                      : "Upload Video"}
                  </button>

                )}


                {!file
                  && selectedJob?.status
                    === "UPLOADED"
                  && (

                    <button
                      type="button"
                      className="primary-button compact-primary"
                      disabled={
                        startingJobId
                        === selectedJob.job_id
                        || (
                          activeJob !== null
                          && activeJob.job_id
                            !== selectedJob.job_id
                        )
                      }
                      onClick={
                        () =>
                          void handleRun(
                            selectedJob.job_id
                          )
                      }
                    >
                      {startingJobId
                        === selectedJob.job_id
                          ? "Starting..."
                          : "Run Analysis"}
                    </button>

                  )}

              </div>

            </div>

          </div>

        </article>


        <article className="panel pipeline-workspace">

          <div className="panel-heading">

            <div>
              <h3>Live Analysis</h3>

              <p>
                End-to-end AutoVue processing
              </p>
            </div>


            <strong className="pipeline-percent">
              {selectedJob
                ? `${selectedJob.progress}%`
                : "0%"}
            </strong>

          </div>


          <div className="pipeline-workspace-body">

            <div className="pipeline-progress-row">

              <progress
                value={
                  selectedJob
                    ?.progress
                  ?? 0
                }
                max={100}
              />

            </div>


            <div className="pipeline-timeline">

              {PIPELINE_STAGES.map(
                (
                  stage,
                  index
                ) => {

                  const className =
                    pipelineStepClass(
                      selectedJob,
                      index
                    );

                  const complete =
                    className.includes(
                      "pipeline-step-complete"
                    );

                  const active =
                    className.includes(
                      "pipeline-step-active"
                    );


                  return (

                    <div
                      key={
                        stage.status
                      }
                      className={
                        className
                      }
                    >

                      <div className="pipeline-marker">
                        {complete
                          ? "✓"
                          : active
                          ? "●"
                          : index + 1}
                      </div>


                      <div className="pipeline-step-copy">

                        <strong>
                          {stage.label}
                        </strong>

                        <span>
                          {stage.description}
                        </span>

                      </div>

                    </div>

                  );

                }
              )}

            </div>


            <div className="pipeline-message">

              {selectedJob
                ? selectedJob.message
                : (
                    "Choose a video to create "
                    + "an AutoVue analysis job."
                  )}

            </div>


            {selectedJob?.status
              === "FAILED"
              && (

                <div className="analysis-alert analysis-alert-error">

                  <strong>
                    Analysis failed
                  </strong>

                  <span>
                    {
                      selectedJob.error
                      ?? (
                        "Check the worker "
                        + "analysis log."
                      )
                    }
                  </span>

                </div>

              )}

          </div>

        </article>

      </section>


      <section className="analysis-output-grid">

        <article className="panel analysis-video-panel">

          <div className="panel-heading">

            <div>
              <h3>Analyzed Output</h3>

              <p>
                Detection and temporal recognition
                output
              </p>
            </div>


            {selectedJob?.status
              === "COMPLETED"
              && (

                <span className="output-ready">
                  ● Ready
                </span>

              )}

          </div>


          <div className="analysis-output-body">

            {selectedJob?.status
              === "COMPLETED"
              && selectedMedia ? (

                <video
                  key={
                    selectedMedia.presentation
                  }
                  src={
                    selectedMedia.presentation
                  }
                  controls
                  preload="metadata"
                />

              ) : (

                <div className="output-placeholder">

                  <div className="output-placeholder-icon">
                    ◉
                  </div>

                  <strong>
                    Analysis output
                  </strong>

                  <span>
                    The rendered AutoVue video
                    appears here when the job
                    completes.
                  </span>

                </div>

              )}

          </div>

        </article>


        <article className="panel recognition-workspace">

          <div className="panel-heading">

            <div>
              <h3>Recognition Result</h3>

              <p>
                Multi-frame plate evidence
              </p>
            </div>


            {results && (

              <span className="reference-badge">
                {recognized.length} candidates
              </span>

            )}

          </div>


          <div className="recognition-workspace-body">

            {resultError && (

              <div className="analysis-alert analysis-alert-error">
                {resultError}
              </div>

            )}


            {!results && !resultError && (

              <div className="recognition-empty">

                <strong>
                  {
                    recognitionPlaceholder
                      .title
                  }
                </strong>

                <span>
                  {
                    recognitionPlaceholder
                      .message
                  }
                </span>

              </div>

            )}


            {results && (

              <>

                <div className="result-summary-grid">

                  <div>
                    <span>
                      Track clusters
                    </span>

                    <strong>
                      {
                        results
                          .summary
                          .conservative_clusters
                      }
                    </strong>
                  </div>


                  <div>
                    <span>
                      Candidates
                    </span>

                    <strong>
                      {
                        results
                          .summary
                          .clusters_with_complete_candidate
                      }
                    </strong>
                  </div>


                  <div>
                    <span>
                      Verified
                    </span>

                    <strong>
                      {
                        results
                          .summary
                          .verified_full
                      }
                    </strong>
                  </div>


                  <div>
                    <span>
                      Review
                    </span>

                    <strong>
                      {
                        results
                          .summary
                          .needs_review
                      }
                    </strong>
                  </div>

                </div>


                {primaryResult && (

                  <div className="primary-recognition">

                    <span>
                      Primary verified evidence
                    </span>

                    <strong>
                      {
                        primaryResult
                          .final_candidate
                      }
                    </strong>

                    <div>

                      <span
                        className={
                          statusClass(
                            primaryResult
                              .status
                          )
                        }
                      >
                        {
                          primaryResult
                            .status
                        }
                      </span>

                      <small>
                        Cluster #
                        {
                          primaryResult
                            .cluster_id
                        }
                      </small>

                    </div>

                  </div>

                )}


                <div className="recognized-list">

                  {recognized.map(
                    (cluster) => (

                      <div
                        className="recognized-row"
                        key={
                          cluster.cluster_id
                        }
                      >

                        <div>

                          <strong>
                            {
                              cluster
                                .final_candidate
                            }
                          </strong>

                          <span>
                            Cluster #
                            {
                              cluster
                                .cluster_id
                            }
                            {" · "}
                            {
                              cluster
                                .full_frame_support
                            }
                            {" full · "}
                            {
                              cluster
                                .fragment_support_frames
                            }
                            {" fragment"}
                          </span>

                        </div>


                        <span
                          className={
                            statusClass(
                              cluster.status
                            )
                          }
                        >
                          {
                            cluster.status
                          }
                        </span>

                      </div>

                    )
                  )}

                </div>


                <div className="result-disclaimer">
                  Evidence status describes the
                  strength of temporal recognition
                  evidence. It is not a ground-truth
                  accuracy claim.
                </div>

              </>

            )}

          </div>

        </article>

      </section>


      <section className="panel recent-jobs modern-jobs-panel">

        <div className="panel-heading">

          <div>
            <h3>Recent Analysis Jobs</h3>

            <p>
              Select previous uploads or reopen
              completed results
            </p>
          </div>


          <span className="reference-badge">
            {jobs.length} jobs
          </span>

        </div>


        {jobs.length === 0 ? (

          <div className="empty-jobs">
            No uploaded jobs yet.
          </div>

        ) : (

          <div className="jobs-table-wrap">

            <table>

              <thead>

                <tr>
                  <th>Video</th>
                  <th>Job</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th />
                </tr>

              </thead>


              <tbody>

                {jobs.map(
                  (job) => (

                    <tr
                      key={
                        job.job_id
                      }
                      className={
                        selectedJob
                          ?.job_id
                        === job.job_id
                          ? "selected-row"
                          : ""
                      }
                    >

                      <td className="job-file-name">
                        {
                          job
                            .original_filename
                        }
                      </td>


                      <td className="job-id">
                        {
                          job.job_id
                            .slice(
                              0,
                              13
                            )
                        }
                        …
                      </td>


                      <td>
                        {formatBytes(
                          job.size_bytes
                        )}
                      </td>


                      <td>

                        <span className="job-status">
                          {humanStage(
                            job.status
                          )}
                        </span>

                      </td>


                      <td>
                        {job.progress}%
                      </td>


                      <td>
                        {jobAction(
                          job
                        )}
                      </td>

                    </tr>

                  )
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>

    </div>
  );
}


export default AnalyzePage;
