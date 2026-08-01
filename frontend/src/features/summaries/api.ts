import { apiRequest } from "../../shared/api/client";
import type { SummaryVersion } from "../../entities/summary/types";

export function getCurrentSummary(nodeId: string) {
  return apiRequest<SummaryVersion | null>(`/api/v1/nodes/${nodeId}/summary`);
}

export function listSummaryVersions(nodeId: string) {
  return apiRequest<SummaryVersion[]>(`/api/v1/nodes/${nodeId}/summary/versions`);
}

export function createSummary(nodeId: string, content: string) {
  return apiRequest<SummaryVersion>(`/api/v1/nodes/${nodeId}/summary`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function activateSummaryVersion(nodeId: string, versionId: string) {
  return apiRequest<SummaryVersion>(
    `/api/v1/nodes/${nodeId}/summary/versions/${versionId}/activate`,
    { method: "POST" },
  );
}

export function updateSummaryVersion(nodeId: string, versionId: string, content: string) {
  return apiRequest<SummaryVersion>(`/api/v1/nodes/${nodeId}/summary/versions/${versionId}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export function deleteSummaryVersion(nodeId: string, versionId: string) {
  return apiRequest<void>(`/api/v1/nodes/${nodeId}/summary/versions/${versionId}`, {
    method: "DELETE",
  });
}
