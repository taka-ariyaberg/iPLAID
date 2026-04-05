import type { BootstrapResponse, JobRecord, RunConfig, LayoutPreview } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      throw new Error(payload.detail ?? "Request failed");
    }
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  async getBootstrap(): Promise<BootstrapResponse> {
    return request<BootstrapResponse>("/api/bootstrap");
  },

  async previewLayout(layoutFile: File): Promise<LayoutPreview> {
    const formData = new FormData();
    formData.append("layout_file", layoutFile);
    return request<LayoutPreview>("/api/layouts/preview", {
      method: "POST",
      body: formData,
    });
  },

  async createRun(params: {
    layoutFile: File;
    metaFile: File;
    config: RunConfig;
  }): Promise<JobRecord> {
    const formData = new FormData();
    formData.append("layout_file", params.layoutFile);
    formData.append("meta_file", params.metaFile);
    formData.append("config_json", JSON.stringify(params.config));

    return request<JobRecord>("/api/runs", {
      method: "POST",
      body: formData,
    });
  },

  async getRun(jobId: string): Promise<JobRecord> {
    return request<JobRecord>(`/api/runs/${jobId}`);
  },

  artifactUrl(jobId: string, artifactName: string): string {
    return `${API_BASE_URL}/api/runs/${jobId}/artifacts/${encodeURIComponent(artifactName)}`;
  },
};