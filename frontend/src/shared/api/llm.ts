import type { LLMSettings } from "../../entities/llm/types";
import { apiRequest } from "./client";

export function getLlmSettings() {
  return apiRequest<LLMSettings>("/api/v1/llm/settings");
}

export function cancelLlmRequest(requestId: string) {
  return apiRequest<void>(`/api/v1/llm-requests/${requestId}/cancel`, { method: "POST" });
}
