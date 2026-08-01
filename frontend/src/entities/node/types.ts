export type NodeType =
  | "TOPIC"
  | "CONCEPT"
  | "THEORY"
  | "METHOD"
  | "QUESTION"
  | "EXAMPLE"
  | "APPLICATION";

export const NODE_TYPES: NodeType[] = [
  "TOPIC",
  "CONCEPT",
  "THEORY",
  "METHOD",
  "QUESTION",
  "EXAMPLE",
  "APPLICATION",
];

/** UI 展示用中文；API 仍传英文枚举值 */
export const NODE_TYPE_LABELS: Record<NodeType, string> = {
  TOPIC: "主题",
  CONCEPT: "概念",
  THEORY: "理论",
  METHOD: "方法",
  QUESTION: "问题",
  EXAMPLE: "例子",
  APPLICATION: "应用",
};

export interface KnowledgeNode {
  id: string;
  graph_id: string;
  title: string;
  node_type: NodeType;
  position_x: number;
  position_y: number;
  created_at: string;
  updated_at: string;
  current_summary_version_id?: string | null;
  summary_preview?: string | null;
}
