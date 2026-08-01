export type AuthorType = "USER" | "LLM" | "LLM_AND_USER";

export interface SummaryVersion {
  id: string;
  node_id: string;
  version_number: number;
  content: string;
  author_type: AuthorType;
  generated_from_message_ids: string[];
  created_at: string;
  is_current: boolean;
}
