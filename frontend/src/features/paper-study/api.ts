import type { PaperConceptMap, PaperConceptItem, PaperKnowledgeInquiry, PaperProblemCard, PaperProblemCardCreate, PaperStudy } from "../../entities/paper-study/types";
import { apiRequest } from "../../shared/api/client";
import { consumeSse, type SseHandler } from "../../shared/api/sse";

export type PaperSourceTextPreview = { filename: string; content: string; character_count: number; extraction_note: string };

export const listStudies = (graphId: string) => apiRequest<PaperStudy[]>(`/api/v1/graphs/${graphId}/paper-studies`);
export const createStudy = (graphId: string, title: string) => apiRequest<PaperStudy>(`/api/v1/graphs/${graphId}/paper-studies`, { method: "POST", body: JSON.stringify({ title }) });
export const getStudy = (id: string) => apiRequest<PaperStudy>(`/api/v1/paper-studies/${id}`);
export const updateStudy = (id: string, title: string) => apiRequest<PaperStudy>(`/api/v1/paper-studies/${id}`, { method: "PATCH", body: JSON.stringify({ title }) });
export const deleteStudy = (id: string) => apiRequest<void>(`/api/v1/paper-studies/${id}`, { method: "DELETE" });
export async function uploadDocument(id: string, file: File) {
  const body = new FormData(); body.append("file", file);
  return apiRequest<PaperStudy["document"]>(`/api/v1/paper-studies/${id}/document`, { method: "POST", body });
}
export const analyzeDocument = (id: string) => apiRequest<PaperStudy>(`/api/v1/paper-studies/${id}/document/analyze`, { method: "POST" });
export const getSourceTextPreview = (id: string) => apiRequest<PaperSourceTextPreview>(`/api/v1/paper-studies/${id}/document/source-text`);
export async function streamConversationStart(id: string, stage: "OVERVIEW" | "PROBLEM_MAP", textModel: string, onEvent: SseHandler, signal?: AbortSignal) {
  const query = new URLSearchParams({ text_model: textModel });
  const response = await fetch(`/api/v1/paper-studies/${id}/conversations/${stage}/start/stream?${query}`, { method: "POST", signal });
  await consumeSse(response, onEvent, signal);
}
export async function streamConversationMessage(id: string, stage: "OVERVIEW" | "PROBLEM_MAP", content: string, textModel: string, onEvent: SseHandler, signal?: AbortSignal) {
  const response = await fetch(`/api/v1/paper-studies/${id}/conversations/messages/stream`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stage, content, text_model: textModel }), signal });
  await consumeSse(response, onEvent, signal);
}
export const createKnowledgeInquiry = (studyId: string, title: string) =>
  apiRequest<PaperKnowledgeInquiry>("/api/v1/paper-studies/" + studyId + "/knowledge-inquiries", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
export const getKnowledgeInquiry = (studyId: string, inquiryId: string) =>
  apiRequest<PaperKnowledgeInquiry>("/api/v1/paper-studies/" + studyId + "/knowledge-inquiries/" + inquiryId);
export async function streamKnowledgeInquiryMessage(
  studyId: string,
  inquiryId: string,
  content: string,
  textModel: string,
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  const response = await fetch("/api/v1/paper-studies/" + studyId + "/knowledge-inquiries/" + inquiryId + "/messages/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, text_model: textModel }),
    signal,
  });
  await consumeSse(response, onEvent, signal);
}
export const saveKnowledgeCard = (studyId: string, inquiryId: string, title: string, summary: string) =>
  apiRequest<{ inquiry: PaperKnowledgeInquiry; node: { id: string } }>(
    "/api/v1/paper-studies/" + studyId + "/knowledge-inquiries/" + inquiryId + "/save-card",
    { method: "POST", body: JSON.stringify({ title, summary }) },
  );
export const discardKnowledgeInquiry = (studyId: string, inquiryId: string) =>
  apiRequest<void>("/api/v1/paper-studies/" + studyId + "/knowledge-inquiries/" + inquiryId + "/discard", { method: "POST" });
export const updateOverview = (id: string, body: Partial<PaperStudy["overview"]>) => apiRequest<PaperStudy>(`/api/v1/paper-studies/${id}/overview`, { method: "PATCH", body: JSON.stringify(body) });
export const createProblemCard = (id: string, body: PaperProblemCardCreate) => apiRequest<PaperProblemCard>(`/api/v1/paper-studies/${id}/problem-cards`, { method: "POST", body: JSON.stringify(body) });
export const updateCard = (id: string, body: Partial<PaperProblemCard>) => apiRequest<PaperProblemCard>(`/api/v1/paper-problem-cards/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteProblemCard = (id: string) => apiRequest<void>(`/api/v1/paper-problem-cards/${id}`, { method: "DELETE" });
export const getConceptMap = (id: string) => apiRequest<PaperConceptMap | null>(`/api/v1/paper-problem-cards/${id}/concept-map`);
export const generateConceptMap = (id: string, textModel: string) => apiRequest<PaperConceptMap>(`/api/v1/paper-problem-cards/${id}/concept-map/generate`, { method: "POST", body: JSON.stringify({ text_model: textModel }) });
export const reviewConceptMap = (id: string, textModel: string) => apiRequest<PaperConceptMap>(`/api/v1/paper-problem-cards/${id}/concept-map/review`, { method: "POST", body: JSON.stringify({ text_model: textModel }) });
export const finalizeConceptMap = (id: string, confirmed_candidate_keys: string[], textModel: string) => apiRequest<PaperConceptMap>(`/api/v1/paper-problem-cards/${id}/concept-map/finalize`, { method: "POST", body: JSON.stringify({ confirmed_candidate_keys, text_model: textModel }) });
export const updateConceptItem = (id: string, user_status: PaperConceptItem["user_status"]) => apiRequest<PaperConceptItem>(`/api/v1/paper-concept-items/${id}`, { method: "PATCH", body: JSON.stringify({ user_status }) });
export const attachConceptNode = (id: string, body: { existing_node_id?: string; create_node?: boolean; position_x?: number; position_y?: number; location?: string; link_type?: string; note?: string }) => apiRequest<PaperConceptItem>(`/api/v1/paper-concept-items/${id}/attach-node`, { method: "POST", body: JSON.stringify(body) });
