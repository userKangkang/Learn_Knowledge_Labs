import { apiRequest } from "../../shared/api/client";
import type { KnowledgeGraph } from "../../entities/graph/types";

export function listGraphs() {
  return apiRequest<KnowledgeGraph[]>("/api/v1/graphs");
}

export function getGraph(graphId: string) {
  return apiRequest<KnowledgeGraph>(`/api/v1/graphs/${graphId}`);
}

export function createGraph(payload: { title: string; description?: string }) {
  return apiRequest<KnowledgeGraph>("/api/v1/graphs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateGraph(graphId: string, payload: { title?: string; description?: string }) {
  return apiRequest<KnowledgeGraph>(`/api/v1/graphs/${graphId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteGraph(graphId: string) {
  return apiRequest<void>(`/api/v1/graphs/${graphId}`, { method: "DELETE" });
}
