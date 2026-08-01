import { apiRequest } from "../../shared/api/client";
import type {
  ContextCandidates,
  ContextPolicy,
  ContextPreview,
  NodeSource,
} from "../../entities/context/types";

export function getContextPolicy(sessionId: string) {
  return apiRequest<ContextPolicy>(`/api/v1/sessions/${sessionId}/context-policy`);
}

export function putContextPolicy(
  sessionId: string,
  payload: {
    include_current_node_summary: boolean;
    max_context_tokens?: number | null;
    sources: NodeSource[];
  },
) {
  return apiRequest<ContextPolicy>(`/api/v1/sessions/${sessionId}/context-policy`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getContextCandidates(sessionId: string) {
  return apiRequest<ContextCandidates>(`/api/v1/sessions/${sessionId}/context-candidates`);
}

export function previewContext(sessionId: string, payload: { new_user_message?: string; persist?: boolean }) {
  return apiRequest<ContextPreview>(`/api/v1/sessions/${sessionId}/context-preview`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
