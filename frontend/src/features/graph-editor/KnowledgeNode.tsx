import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { NODE_TYPE_LABELS, type NodeType } from "../../entities/node/types";

export type KnowledgeFlowNode = Node<
  {
    title: string;
    nodeType: NodeType;
    summaryPreview?: string | null;
  },
  "knowledge"
>;

const TYPE_COLORS: Record<NodeType, string> = {
  TOPIC: "#1f6f5b",
  CONCEPT: "#2f5d8c",
  THEORY: "#6b4c9a",
  METHOD: "#9a6b2f",
  QUESTION: "#8c3b3b",
  EXAMPLE: "#3b6b8c",
  APPLICATION: "#2f7a4b",
};

export function KnowledgeNodeView({ data, selected }: NodeProps<KnowledgeFlowNode>) {
  const accent = TYPE_COLORS[data.nodeType] ?? "#2f5d8c";
  const summary = data.summaryPreview?.trim();

  return (
    <div className={`k-node ${selected ? "k-node--selected" : ""}`} style={{ borderColor: accent }}>
      {/* With ConnectionMode.Loose, each side works as both source and target. */}
      <Handle type="source" id="top" position={Position.Top} className="k-handle" />
      <Handle type="source" id="right" position={Position.Right} className="k-handle" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="k-handle" />
      <Handle type="source" id="left" position={Position.Left} className="k-handle" />

      <div className="k-node__type" style={{ color: accent }}>
        {NODE_TYPE_LABELS[data.nodeType]}
      </div>
      <div className="k-node__title">{data.title || "未命名节点"}</div>
      <div className={`k-node__summary ${summary ? "" : "k-node__summary--empty"}`}>
        {summary || "暂无摘要"}
      </div>
      <div className="k-node__meta">选中后 Tab 子节点 · Enter 兄弟</div>
    </div>
  );
}
