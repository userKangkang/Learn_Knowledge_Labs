export type MessageRole = "USER" | "ASSISTANT" | "SYSTEM";
export type MessageStatus = "ACTIVE" | "EDITED" | "DELETED" | "STREAMING" | "FAILED";

export interface MessageAttachment {
  id: string;
  session_id: string;
  message_id: string | null;
  filename: string;
  content_type: string;
  kind?: string;
  size_bytes: number;
  extract_status: "PENDING" | "SUCCEEDED" | "FAILED" | "SKIPPED";
  extract_error?: string | null;
  has_extracted_text: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  current_revision: number;
  llm_request_id?: string | null;
  provider?: string | null;
  attachments?: MessageAttachment[];
  created_at: string;
  updated_at: string;
}

export interface MessageRevision {
  id: string;
  message_id: string;
  revision_number: number;
  content: string;
  created_at: string;
}
