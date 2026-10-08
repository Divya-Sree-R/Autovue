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
