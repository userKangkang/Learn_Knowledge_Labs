import { ApiError, apiRequest } from "../../shared/api/client";
import { consumeSse, type SseHandler } from "../../shared/api/sse";
import type { LLMSettings } from "../../entities/llm/types";
import type {
  ChatMessage,
  MessageAttachment,
  MessageRevision,
  MessageRole,
} from "../../entities/message/types";
import type { ConversationSession } from "../../entities/session/types";

export function listSessions(nodeId: string) {
  return apiRequest<ConversationSession[]>(`/api/v1/nodes/${nodeId}/sessions`);
}

export function createSession(nodeId: string, title?: string) {
  return apiRequest<ConversationSession>(`/api/v1/nodes/${nodeId}/sessions`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function updateSession(sessionId: string, title: string) {
  return apiRequest<ConversationSession>(`/api/v1/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteSession(sessionId: string) {
  return apiRequest<void>(`/api/v1/sessions/${sessionId}`, { method: "DELETE" });
}

export function listMessages(sessionId: string) {
  return apiRequest<ChatMessage[]>(`/api/v1/sessions/${sessionId}/messages`);
}

export function createMessage(sessionId: string, role: MessageRole, content: string) {
  return apiRequest<ChatMessage>(`/api/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role, content }),
  });
}

export function updateMessage(messageId: string, content: string) {
  return apiRequest<ChatMessage>(`/api/v1/messages/${messageId}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export function deleteMessage(messageId: string) {
  return apiRequest<void>(`/api/v1/messages/${messageId}`, { method: "DELETE" });
}

export function listRevisions(messageId: string) {
  return apiRequest<MessageRevision[]>(`/api/v1/messages/${messageId}/revisions`);
}

export function getLlmSettings() {
  return apiRequest<LLMSettings>("/api/v1/llm/settings");
}

export async function uploadAttachment(sessionId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`/api/v1/sessions/${sessionId}/attachments`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    try {
      const body = await response.json();
      throw new ApiError(
        response.status,
        body?.error?.code ?? "UNKNOWN_ERROR",
        body?.error?.message ?? response.statusText,
      );
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(response.status, "UNKNOWN_ERROR", response.statusText);
    }
  }
  return response.json() as Promise<MessageAttachment>;
}

export async function streamMessage(
  sessionId: string,
  body: {
    content: string;
    attachment_ids?: string[];
    web_search?: boolean;
    text_model?: "deepseek-v4-pro" | "kimi-k2.6";
  },
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  const response = await fetch(`/api/v1/sessions/${sessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  await consumeSse(response, onEvent, signal);
}

export async function retryStreamMessage(
  sessionId: string,
  body: {
    web_search?: boolean;
    text_model?: "deepseek-v4-pro" | "kimi-k2.6";
  },
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  const response = await fetch(`/api/v1/sessions/${sessionId}/messages/retry/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  await consumeSse(response, onEvent, signal);
}

export function cancelLlmRequest(requestId: string) {
  return apiRequest<void>(`/api/v1/llm-requests/${requestId}/cancel`, { method: "POST" });
}
