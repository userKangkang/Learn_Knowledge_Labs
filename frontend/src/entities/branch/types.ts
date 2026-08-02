import type { ChatMessage } from "../message/types";

export interface TempTurn {
  role: "USER" | "ASSISTANT";
  content: string;
}

export interface ConversationBranch {
  id: string;
  session_id: string;
  anchor_message_id: string;
  title?: string | null;
  message_count: number;
  created_at: string;
  messages: ChatMessage[];
}
