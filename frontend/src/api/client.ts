import type { Analysis, AnalysisCreated, CreateAnalysisRequest, HistoryItem, ModelProfile, Problem, RunEvent, ValidationProfile } from "./contract";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const problem = await response.json().catch(() => ({ detail: "No fue posible completar la solicitud." })) as Problem;
    throw new Error(problem.detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  models: () => request<{ models: ModelProfile[] }>("/api/v1/config/models"),
  validationProfiles: () => request<{ validation_profiles: ValidationProfile[] }>("/api/v1/config/validation-profiles"),
  createAnalysis: (payload: CreateAnalysisRequest) => request<AnalysisCreated>("/api/v1/analyses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  analysis: (id: string) => request<Analysis>(`/api/v1/analyses/${id}`),
  history: (status?: string) => request<{ items: HistoryItem[] }>(`/api/v1/analyses${status ? `?status_filter=${encodeURIComponent(status)}` : ""}`),
  events: (id: string) => request<{ items: RunEvent[] }>(`/api/v1/analyses/${id}/events`),
};
