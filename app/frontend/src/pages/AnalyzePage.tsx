import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getJobs,
  runJob,
  uploadVideo,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";


const ACTIVE_STATUSES = new Set([
  "QUEUED",
  "DETECTING_TRACKING",
  "OCR_PROCESSING",
  "TEMPORAL_CONSENSUS",
  "RENDERING",
]);


const PIPELINE_STAGES = [
  "UPLOADED",
  "QUEUED",
  "DETECTING_TRACKING",
  "OCR_PROCESSING",
  "TEMPORAL_CONSENSUS",
  "RENDERING",
  "COMPLETED",
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


function AnalyzePage() {

  const [file, setFile] =
    useState<File | null>(null);

  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [uploading, setUploading] =
    useState(false);

  const [
    startingJobId,
    setStartingJobId,
  ] = useState<string | null>(
    null
  );

  const [error, setError] =
    useState<string | null>(null);

  const [
    createdJob,
    setCreatedJob,
  ] = useState<AnalysisJob | null>(
    null
  );


  // -------------------------------------------------------
  // Job history + live polling
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

        setJobs(latest);

        setCreatedJob(
          (current) => {

            if (!current) {
              return current;
            }

            return (
              latest.find(
                (item) =>
                  item.job_id ===
                  current.job_id
              )
              ?? current
            );
          }
        );

      } catch {
        // Keep the page usable if polling
        // temporarily fails.
      }
    }


    void refreshJobs();


    const timer = window.setInterval(
      () => {
        void refreshJobs();
      },
      2000
    );


    return () => {
      cancelled = true;

      window.clearInterval(
        timer
      );
    };

  }, []);


  const filePreview = useMemo(
    () => {

      if (!file) {
        return null;
      }

      return {
        name:
          file.name,

        size:
          formatBytes(
            file.size
          ),

        type:
          file.type
          || "video/mp4",
      };

    },
    [file]
  );


  function handleFile(
    selected: File | null
  ) {

    setError(null);

    setCreatedJob(null);


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
  }


  async function handleUpload() {

    if (
      !file
      || uploading
    ) {
      return;
    }


    setUploading(true);

    setError(null);


    try {

      const job =
        await uploadVideo(
          file
        );


      setCreatedJob(
        job
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


      setFile(null);

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : "Video upload failed."
      );

    } finally {

      setUploading(false);

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

    setError(null);


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


      setCreatedJob(
        (current) =>
          current?.job_id
          === job.job_id
            ? job
            : current
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


  function actionForJob(
    job: AnalysisJob
  ) {

    if (
      job.status
      === "UPLOADED"
    ) {

      const starting =
        startingJobId
        === job.job_id;


      return (
        <button
          type="button"
          className="secondary-button"
          disabled={
            starting
          }
          onClick={() =>
            void handleRun(
              job.job_id
            )
          }
        >
          {starting
            ? "Starting..."
            : "Run Analysis"}
        </button>
      );
    }


    if (
      ACTIVE_STATUSES.has(
        job.status
      )
    ) {
      return (
        <span>
          Running…
        </span>
      );
    }


    if (
      job.status
      === "COMPLETED"
    ) {
      return (
        <span>
          Complete
        </span>
      );
    }


    if (
      job.status
      === "FAILED"
    ) {
      return (
        <span>
          Failed
        </span>
      );
    }


    return (
      <span>—</span>
    );
  }


  return (
    <div className="analyze-page">

      <header className="route-header">

        <span className="route-eyebrow">
          AutoVue
        </span>

        <h2>
          Analyze Video
        </h2>

        <p>
          Upload an MP4 road video,
          then run the complete AutoVue
          recognition pipeline.
        </p>

      </header>


      <section className="upload-grid">

        <div className="panel upload-panel">

          <div className="panel-heading">

            <div>

              <h3>
                Video Input
              </h3>

              <p>
                MP4 · maximum 500 MB
              </p>

            </div>

          </div>


          <div className="upload-content">

            <label className="upload-dropzone">

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


              <div className="upload-icon">
                ↑
              </div>


              <strong>
                Select road video
              </strong>


              <span>
                Choose an MP4 file
                from this computer
              </span>

            </label>


            {filePreview && (

              <div className="selected-file">

                <div>

                  <strong>
                    {filePreview.name}
                  </strong>

                  <span>
                    {filePreview.size}
                    {" · "}
                    {filePreview.type}
                  </span>

                </div>


                <button
                  type="button"
                  className="secondary-button"
                  onClick={
                    () =>
                      setFile(null)
                  }
                >
                  Remove
                </button>

              </div>

            )}


            {error && (

              <div className="upload-error">
                {error}
              </div>

            )}


            <button
              type="button"
              className="primary-button"
              disabled={
                !file
                || uploading
              }
              onClick={
                () =>
                  void handleUpload()
              }
            >
              {uploading
                ? "Uploading..."
                : "Create Analysis Job"}
            </button>


            <div className="upload-note">

              Uploading creates a job
              without starting GPU
              inference automatically.

              <br />

              After upload, choose
              <strong>
                {" Run Analysis "}
              </strong>
              to start detection,
              tracking, OCR and
              temporal reasoning.

            </div>

          </div>

        </div>


        <div className="panel workflow-panel">

          <div className="panel-heading">

            <div>

              <h3>
                Analysis Pipeline
              </h3>

              <p>
                Live job lifecycle
              </p>

            </div>

          </div>


          <div className="workflow-list">

            {PIPELINE_STAGES.map(
              (
                stage,
                index
              ) => (

                <div
                  className="workflow-stage"
                  key={stage}
                >

                  <span>
                    {index + 1}
                  </span>

                  <strong>
                    {humanStage(
                      stage
                    )}
                  </strong>

                </div>

              )
            )}

          </div>

        </div>

      </section>


      {createdJob && (

        <section className="panel created-job">

          <div className="panel-heading">

            <div>

              <h3>
                Analysis Job
              </h3>

              <p>
                Live AutoVue
                processing status
              </p>

            </div>


            <span className="job-status">
              {humanStage(
                createdJob.status
              )}
            </span>

          </div>


          <div className="job-details">

            <div>

              <span>
                Job ID
              </span>

              <strong className="job-id">
                {createdJob.job_id}
              </strong>

            </div>


            <div>

              <span>
                Filename
              </span>

              <strong>
                {
                  createdJob
                    .original_filename
                }
              </strong>

            </div>


            <div>

              <span>
                Size
              </span>

              <strong>
                {formatBytes(
                  createdJob.size_bytes
                )}
              </strong>

            </div>


            <div>

              <span>
                Progress
              </span>

              <strong>
                {createdJob.progress}%
              </strong>

            </div>

          </div>


          <progress
            value={
              createdJob.progress
            }
            max={100}
            style={{
              width: "100%",
            }}
          />


          <div className="job-message">
            {createdJob.message}
          </div>


          {createdJob.error && (

            <div className="upload-error">
              {createdJob.error}
            </div>

          )}


          {createdJob.status
            === "UPLOADED"
            && (

              <button
                type="button"
                className="primary-button"
                disabled={
                  startingJobId
                  === createdJob.job_id
                }
                onClick={
                  () =>
                    void handleRun(
                      createdJob.job_id
                    )
                }
              >
                {startingJobId
                  === createdJob.job_id
                    ? "Starting Analysis..."
                    : "Run Analysis"}
              </button>

            )}


          {ACTIVE_STATUSES.has(
            createdJob.status
          ) && (

            <div className="upload-note">
              AutoVue is processing this
              video. This page refreshes
              the job status automatically.
            </div>

          )}


          {createdJob.status
            === "COMPLETED"
            && (

              <div className="upload-note">

                Analysis complete.

                <br />

                The canonical recognition
                result and analyzed video
                are now available for this
                job.

              </div>

            )}

        </section>

      )}


      <section className="panel recent-jobs">

        <div className="panel-heading">

          <div>

            <h3>
              Recent Jobs
            </h3>

            <p>
              Local AutoVue
              analysis workspace
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
                  <th>File</th>
                  <th>Job ID</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Action</th>
                </tr>

              </thead>


              <tbody>

                {jobs.map(
                  (job) => (

                    <tr
                      key={
                        job.job_id
                      }
                    >

                      <td className="plate-value">
                        {
                          job
                            .original_filename
                        }
                      </td>


                      <td className="job-id">
                        {
                          job.job_id
                        }
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
                        {actionForJob(
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
