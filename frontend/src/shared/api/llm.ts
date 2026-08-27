import type { LLMSettings } from "../../entities/llm/types";
import { apiRequest } from "./client";

export function getLlmSettings() {
  return apiRequest<LLMSettings>("/api/v1/llm/settings");
}

export type LLMConnectionTestResult = {
  ok: boolean;
  provider: string;
  model: string;
  response: string;
  latency_ms: number;
};

export function testLlmConnection(textModel: string) {
  return apiRequest<LLMConnectionTestResult>("/api/v1/llm/test-connection", {
    method: "POST",
    body: JSON.stringify({ text_model: textModel }),
  });
}

export function cancelLlmRequest(requestId: string) {
  return apiRequest<void>(`/api/v1/llm-requests/${requestId}/cancel`, { method: "POST" });
}
