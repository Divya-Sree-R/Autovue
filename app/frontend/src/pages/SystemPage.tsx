import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getHealth,
  getJobs,
} from "../services/api";

import type {
  AnalysisJob,
  HealthResponse,
} from "../services/api";


const RUNNING_STATUSES =
  new Set([
    "QUEUED",
    "DETECTING_TRACKING",
    "OCR_PROCESSING",
    "TEMPORAL_CONSENSUS",
    "RENDERING",
  ]);


function humanStatus(
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


function SystemPage() {
  const [jobs, setJobs] =
    useState<AnalysisJob[]>([]);

  const [health, setHealth] =
    useState<HealthResponse | null>(
      null
    );

  const [healthError, setHealthError] =
    useState(false);


  useEffect(() => {
    let cancelled = false;


    async function refresh() {
      try {
        const [
          healthResult,
          jobResult,
        ] = await Promise.all([
          getHealth(),
          getJobs(),
        ]);

        if (cancelled) {
          return;
        }

        setHealth(
          healthResult
        );

        setJobs(
          jobResult
        );

        setHealthError(
          false
        );

      } catch {
        if (!cancelled) {
          setHealthError(
            true
          );
        }
      }
    }


    void refresh();


    const interval =
      window.setInterval(
        () => {
          void refresh();
        },
        4000
      );


    return () => {
      cancelled = true;

      window.clearInterval(
        interval
      );
    };
  }, []);


  const activeJob =
    useMemo(
      () =>
        jobs.find(
          (job) =>
            RUNNING_STATUSES.has(
              job.status
            )
        ) ?? null,
      [jobs]
    );


  const completed =
    jobs.filter(
      (job) =>
        job.status
        === "COMPLETED"
    ).length;


  const failed =
    jobs.filter(
      (job) =>
        job.status
        === "FAILED"
    ).length;


  return (
    <div className="system-monitor-page">

      <header className="route-header system-monitor-header">

        <div>

          <span className="route-eyebrow">
            AutoVue
          </span>

          <h2>
            System Health
          </h2>

          <p>
            Live operational status of
            the AutoVue analysis service.
          </p>

        </div>


        <div
          className={
            healthError
              ? (
                  "system-health-pill "
                  + "system-health-offline"
                )
              : "system-health-pill"
          }
        >

          <span />

          {healthError
            ? "Service unavailable"
            : health
              ? "System operational"
              : "Checking system"}

        </div>

      </header>


      <section className="system-kpi-grid">

        <article className="system-kpi">

          <div className="system-kpi-icon">
            API
          </div>

          <div>

            <span>
              API
            </span>

            <strong>
              {healthError
                ? "Offline"
                : "Online"}
            </strong>

            <small>
              Backend service
            </small>

          </div>

        </article>


        <article className="system-kpi">

          <div className="system-kpi-icon">
            GPU
          </div>

          <div>

            <span>
              Analysis Worker
            </span>

            <strong>
              {activeJob
                ? "Processing"
                : "Ready"}
            </strong>

            <small>
              GPU inference
            </small>

          </div>

        </article>


        <article className="system-kpi">

          <div className="system-kpi-icon">
            ✓
          </div>

          <div>

            <span>
              Completed
            </span>

            <strong>
              {completed}
            </strong>

            <small>
              Analysis jobs
            </small>

          </div>

        </article>


        <article className="system-kpi">

          <div
            className={
              failed > 0
                ? (
                    "system-kpi-icon "
                    + "system-kpi-icon-warning"
                  )
                : "system-kpi-icon"
            }
          >
            !
          </div>

          <div>

            <span>
              Failed
            </span>

            <strong>
              {failed}
            </strong>

            <small>
              Jobs requiring attention
            </small>

          </div>

        </article>

      </section>


      {activeJob ? (

        <section className="panel system-live-panel">

          <div className="panel-heading">

            <div>

              <h3>
                Active Analysis
              </h3>

              <p>
                Currently processing
                road video
              </p>

            </div>


            <span className="system-active-badge">
              ● Processing
            </span>

          </div>


          <div className="system-active-job">

            <div>

              <span>
                Video
              </span>

              <strong>
                {
                  activeJob
                    .original_filename
                }
              </strong>

            </div>


            <div>

              <span>
                Stage
              </span>

              <strong>
                {
                  humanStatus(
                    activeJob.status
                  )
                }
              </strong>

            </div>


            <div>

              <span>
                Progress
              </span>

              <strong>
                {
                  activeJob.progress
                }%
              </strong>

            </div>

          </div>


          <div
            className="system-progress-track"
          >
            <span
              style={{
                width:
                  `${activeJob.progress}%`,
              }}
            />
          </div>

        </section>

      ) : (

        <section className="panel system-idle-panel">

          <div className="system-idle-icon">
            ✓
          </div>

          <div>

            <h3>
              Analysis worker ready
            </h3>

            <p>
              No road video is currently
              being processed.
            </p>

          </div>

        </section>

      )}


      <section className="panel system-activity-panel">

        <div className="panel-heading">

          <div>

            <h3>
              Recent Activity
            </h3>

            <p>
              Latest AutoVue analysis jobs
            </p>

          </div>


          <span className="reference-badge">
            {jobs.length}
            {" jobs"}
          </span>

        </div>


        {jobs.length === 0 ? (

          <div className="dashboard-empty-inline">
            No analysis jobs yet.
          </div>

        ) : (

          <div className="table-wrapper">

            <table>

              <thead>

                <tr>
                  <th>Video</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Job ID</th>
                </tr>

              </thead>


              <tbody>

                {jobs
                  .slice(
                    0,
                    8
                  )
                  .map(
                    (job) => (

                      <tr
                        key={
                          job.job_id
                        }
                      >

                        <td>
                          <strong>
                            {
                              job
                                .original_filename
                            }
                          </strong>
                        </td>

                        <td>
                          <span className="job-status">
                            {
                              humanStatus(
                                job.status
                              )
                            }
                          </span>
                        </td>

                        <td>
                          {
                            job.progress
                          }%
                        </td>

                        <td className="job-id">
                          {
                            job.job_id
                              .slice(
                                0,
                                12
                              )
                          }…
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


export default SystemPage;
