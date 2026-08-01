export type EdgeType =
  | "IS_A"
  | "PART_OF"
  | "PREREQUISITE_OF"
  | "EXAMPLE_OF"
  | "CAUSES_OR_LEADS_TO"
  | "CONTRASTS_WITH"
  | "APPLIES_TO"
  | "CUSTOM";

export const EDGE_TYPES: EdgeType[] = [
  "IS_A",
  "PART_OF",
  "PREREQUISITE_OF",
  "EXAMPLE_OF",
  "CAUSES_OR_LEADS_TO",
  "CONTRASTS_WITH",
  "APPLIES_TO",
  "CUSTOM",
];

/** UI 展示用中文；API 仍传英文枚举值 */
export const EDGE_TYPE_LABELS: Record<EdgeType, string> = {
  IS_A: "是一种",
  PART_OF: "组成部分",
  PREREQUISITE_OF: "前置知识",
  EXAMPLE_OF: "示例",
  CAUSES_OR_LEADS_TO: "导致/促进",
  CONTRASTS_WITH: "对比",
  APPLIES_TO: "应用于",
  CUSTOM: "自定义",
};

export function getEdgeDisplayLabel(type: EdgeType, customLabel?: string | null): string {
  if (type === "CUSTOM" && customLabel?.trim()) {
    return customLabel.trim();
  }
  return EDGE_TYPE_LABELS[type];
}

export interface KnowledgeEdge {
  id: string;
  graph_id: string;
  source_node_id: string;
  target_node_id: string;
  type: EdgeType;
  custom_label?: string | null;
  created_at: string;
  updated_at: string;
}
