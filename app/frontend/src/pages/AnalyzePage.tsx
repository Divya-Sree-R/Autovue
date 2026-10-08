import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getJobs,
  uploadVideo,
} from "../services/api";

import type {
  AnalysisJob,
} from "../services/api";


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


function AnalyzePage() {
  const [file, setFile] =
    useState<File | null>(null);

  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [uploading, setUploading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [createdJob, setCreatedJob] =
    useState<AnalysisJob | null>(null);


  useEffect(() => {
    getJobs()
      .then(setJobs)
      .catch(() => {
        // Job history is secondary to uploading,
        // so keep the page usable if listing fails.
      });
  }, []);


  const filePreview = useMemo(() => {
    if (!file) {
      return null;
    }

    return {
      name: file.name,
      size: formatBytes(file.size),
      type: file.type || "video/mp4",
    };
  }, [file]);


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

    setFile(selected);
  }


  async function handleUpload() {
    if (!file || uploading) {
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const job =
        await uploadVideo(file);

      setCreatedJob(job);

      setJobs((previous) => [
        job,
        ...previous.filter(
          (item) =>
            item.job_id !==
            job.job_id
        ),
      ]);

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


  return (
    <div className="analyze-page">

      <header className="route-header">

        <span className="route-eyebrow">
          AutoVue
        </span>

        <h2>Analyze Video</h2>

        <p>
          Upload an MP4 road video to create
          an AutoVue analysis job.
        </p>

      </header>


      <section className="upload-grid">

        <div className="panel upload-panel">

          <div className="panel-heading">

            <div>
              <h3>Video Input</h3>

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
                onChange={(event) =>
                  handleFile(
                    event.target.files?.[0]
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
                Choose an MP4 file from
                this computer
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
                  onClick={() =>
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
                !file ||
                uploading
              }
              onClick={
                handleUpload
              }
            >
              {uploading
                ? "Uploading..."
                : "Create Analysis Job"}
            </button>


            <div className="upload-note">

              Creating a job stores the input
              video securely in the local
              AutoVue job workspace.

              <br />

              Detection, OCR and temporal
              inference are not started by
              this upload step yet.

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
                Planned job lifecycle
              </p>
            </div>

          </div>


          <div className="workflow-list">

            {[
              "UPLOADED",
              "QUEUED",
              "DETECTING_TRACKING",
              "OCR_PROCESSING",
              "TEMPORAL_CONSENSUS",
              "RENDERING",
              "COMPLETED",
            ].map(
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
                    {stage.replaceAll(
                      "_",
                      " "
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
              <h3>Job Created</h3>
              <p>
                AutoVue accepted the video
              </p>
            </div>

            <span className="job-status">
              {createdJob.status}
            </span>

          </div>


          <div className="job-details">

            <div>
              <span>Job ID</span>

              <strong className="job-id">
                {createdJob.job_id}
              </strong>
            </div>

            <div>
              <span>Filename</span>

              <strong>
                {
                  createdJob
                    .original_filename
                }
              </strong>
            </div>

            <div>
              <span>Size</span>

              <strong>
                {formatBytes(
                  createdJob.size_bytes
                )}
              </strong>
            </div>

            <div>
              <span>Status</span>

              <strong>
                {createdJob.status}
              </strong>
            </div>

          </div>


          <div className="job-message">
            {createdJob.message}
          </div>

        </section>

      )}


      <section className="panel recent-jobs">

        <div className="panel-heading">

          <div>
            <h3>Recent Jobs</h3>

            <p>
              Local AutoVue analysis workspace
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
                </tr>
              </thead>

              <tbody>

                {jobs.map(
                  (job) => (
                    <tr
                      key={job.job_id}
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
                          {job.status}
                        </span>
                      </td>

                      <td>
                        {job.progress}%
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
