import { apiRequest } from "../../shared/api/client";
import { consumeSse, type SseHandler } from "../../shared/api/sse";
export { cancelLlmRequest, getLlmSettings } from "../../shared/api/llm";
import type {
  ProblemCardLink,
  ProblemLinkType,
  ProblemMapBundle,
  ProblemMapApplyRequest,
  ProblemMapApplyResult,
  ProblemMapPosition,
  ProblemMapSuggestResponse,
  RelatedPaperSearchTurn,
  SharedProblem,
  SharedProblemEdge,
} from "../../entities/problem-map/types";

export function getProblemMap(graphId: string) {
  return apiRequest<ProblemMapBundle>(`/api/v1/graphs/${graphId}/problem-map`);
}

export function createProblem(graphId: string, payload: { title: string; description?: string }) {
  return apiRequest<SharedProblem>(`/api/v1/graphs/${graphId}/problems`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProblem(problemId: string, payload: { title?: string; description?: string }) {
  return apiRequest<SharedProblem>(`/api/v1/problems/${problemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProblem(problemId: string) {
  return apiRequest<void>(`/api/v1/problems/${problemId}`, { method: "DELETE" });
}

export function createProblemEdge(
  graphId: string,
  payload: { source_problem_id: string; target_problem_id: string; relation_label?: string },
) {
  return apiRequest<SharedProblemEdge>(`/api/v1/graphs/${graphId}/problem-edges`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProblemEdge(edgeId: string, payload: { relation_label?: string; reverse?: boolean }) {
  return apiRequest<SharedProblemEdge>(`/api/v1/problem-edges/${edgeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProblemEdge(edgeId: string) {
  return apiRequest<void>(`/api/v1/problem-edges/${edgeId}`, { method: "DELETE" });
}

export function createCardLink(
  cardId: string,
  payload: { shared_problem_id: string; link_type?: ProblemLinkType },
) {
  return apiRequest<ProblemCardLink>(`/api/v1/problem-cards/${cardId}/links`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCardLink(linkId: string, payload: { link_type: ProblemLinkType }) {
  return apiRequest<ProblemCardLink>(`/api/v1/card-links/${linkId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCardLink(linkId: string) {
  return apiRequest<void>(`/api/v1/card-links/${linkId}`, { method: "DELETE" });
}

export function savePositions(
  graphId: string,
  items: Array<{
    entity_type: "PAPER" | "CARD" | "PROBLEM";
    entity_id: string;
    position_x: number;
    position_y: number;
  }>,
) {
  return apiRequest<ProblemMapPosition[]>(`/api/v1/graphs/${graphId}/problem-map/positions`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
}

export function suggestProblemMap(graphId: string, textModel: string) {
  return apiRequest<ProblemMapSuggestResponse>(`/api/v1/graphs/${graphId}/problem-map/suggest`, {
    method: "POST",
    body: JSON.stringify({ text_model: textModel }),
  });
}

export function applyProblemMap(graphId: string, payload: ProblemMapApplyRequest) {
  return apiRequest<ProblemMapApplyResult>(`/api/v1/graphs/${graphId}/problem-map/apply`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function streamRelatedPaperSearch(
  graphId: string,
  body: {
    study_ids: string[];
    model: string;
    prompt: string;
    ccf_a_only: boolean;
    prior_turns: RelatedPaperSearchTurn[];
  },
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  const response = await fetch(`/api/v1/graphs/${graphId}/problem-map/related-paper-search/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  await consumeSse(response, onEvent, signal);
}
