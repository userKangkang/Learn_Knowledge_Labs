export type ConversationMode = "NONE" | "LAST_N_TURNS" | "SELECTED_MESSAGES" | "FULL_SESSION";

export interface SessionSource {
  id?: string;
  source_session_id: string;
  conversation_mode: ConversationMode;
  last_n_turns?: number | null;
  selected_message_ids?: string[];
  order_index: number;
}

export interface NodeSource {
  id?: string;
  source_node_id: string;
  include_summary: boolean;
  order_index: number;
  is_same_node?: boolean;
  is_ancestor?: boolean;
  sessions: SessionSource[];
}

export interface ContextPolicy {
  id: string;
  session_id: string;
  node_id: string;
  include_current_node_summary: boolean;
  include_current_session_history: boolean;
  max_context_tokens?: number | null;
  policy_version: number;
  sources: NodeSource[];
  created_at: string;
  updated_at: string;
}

export interface CandidateNode {
  id: string;
  title: string;
  node_type: string;
  generation?: number | null;
}

export interface ContextCandidates {
  ancestors: CandidateNode[];
  non_ancestors: CandidateNode[];
}

export interface ContextPreview {
  snapshot_id?: string | null;
  policy_version: number;
  rendered_system_prompt: string;
  rendered_context: string;
  estimated_input_tokens: number;
  truncated: boolean;
  items: Array<{
    source_type: string;
    rendered_content: string;
    order_index: number;
  }>;
}

export const CONVERSATION_MODE_LABELS: Record<Exclude<ConversationMode, "NONE">, string> = {
  FULL_SESSION: "整场会话",
  LAST_N_TURNS: "最近 N 轮",
  SELECTED_MESSAGES: "指定消息",
};
