import type {
  AutoVueResult,
  ClusterResult,
} from "../types/autovue";

export const API_BASE =
  import.meta.env.VITE_API_BASE ??
  "http://127.0.0.1:8000";

export async function getReferenceResults(): Promise<AutoVueResult> {
  const response = await fetch(
    `${API_BASE}/api/reference/results`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load AutoVue results: ${response.status}`
    );
  }

  return response.json();
}

export async function getCluster(
  clusterId: number
): Promise<ClusterResult> {
  const response = await fetch(
    `${API_BASE}/api/reference/clusters/${clusterId}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load cluster ${clusterId}`
    );
  }

  return response.json();
}

export const mediaUrls = {
  original:
    `${API_BASE}/api/reference/video/original`,

  analyzed:
    `${API_BASE}/api/reference/video/analyzed`,
};

export function cropUrl(filename: string) {
  return (
    `${API_BASE}/api/reference/crops/` +
    encodeURIComponent(filename)
  );
}


export interface AnalysisJob {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  original_filename: string;
  stored_filename: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
  updated_at: string;
  error: string | null;
}


export async function getJobs(): Promise<AnalysisJob[]> {
  const response = await fetch(
    `${API_BASE}/api/jobs`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load jobs: ${response.status}`
    );
  }

  const data = await response.json();

  return data.jobs;
}


export async function getJob(
  jobId: string
): Promise<AnalysisJob> {

  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load job ${jobId}`
    );
  }

  return response.json();
}


export async function uploadVideo(
  file: File
): Promise<AnalysisJob> {

  const formData = new FormData();

  formData.append(
    "file",
    file
  );

  const response = await fetch(
    `${API_BASE}/api/jobs`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    let message =
      `Upload failed: ${response.status}`;

    try {
      const data = await response.json();

      if (data.detail) {
        message = data.detail;
      }
    } catch {
      // Keep default error message.
    }

    throw new Error(message);
  }

  return response.json();
}


async function apiErrorMessage(
  response: Response,
  fallback: string
): Promise<string> {
  try {
    const data = await response.json();

    if (
      data &&
      typeof data.detail === "string"
    ) {
      return data.detail;
    }
  } catch {
    // Ignore non-JSON error bodies.
  }

  return fallback;
}


export async function runJob(
  jobId: string
): Promise<AnalysisJob> {

  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}/run`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    throw new Error(
      await apiErrorMessage(
        response,
        `Could not start analysis: ${response.status}`
      )
    );
  }

  return response.json();
}


export async function getJobResults(
  jobId: string
): Promise<AutoVueResult> {

  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}/results`
  );

  if (!response.ok) {
    throw new Error(
      await apiErrorMessage(
        response,
        `Could not load job results: ${response.status}`
      )
    );
  }

  return response.json();
}


export async function getJobCluster(
  jobId: string,
  clusterId: number
): Promise<ClusterResult> {

  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}/clusters/${clusterId}`
  );

  if (!response.ok) {
    throw new Error(
      await apiErrorMessage(
        response,
        `Could not load cluster ${clusterId}`
      )
    );
  }

  return response.json();
}


export function jobMediaUrls(
  jobId: string
) {
  return {
    original:
      `${API_BASE}/api/jobs/${jobId}/video/original`,

    tracking:
      `${API_BASE}/api/jobs/${jobId}/video/tracking`,

    analyzed:
      `${API_BASE}/api/jobs/${jobId}/video/analyzed`,
  };
}


export function jobCropUrl(
  jobId: string,
  filename: string
) {
  return (
    `${API_BASE}/api/jobs/${jobId}/crops/` +
    encodeURIComponent(filename)
  );
}
