import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

export type ProblemFlowNode = Node<
  {
    title: string;
    description: string;
    isRoot: boolean;
    coveragePaperCount: number;
    coverageCoreCount: number;
    coverageTouchedCount: number;
  },
  "problem"
>;

export function ProblemNodeView({ data, selected }: NodeProps<ProblemFlowNode>) {
  const badge =
    data.coveragePaperCount > 0
      ? `覆盖 ${data.coveragePaperCount} 篇 · 核心 ${data.coverageCoreCount} · 提及 ${data.coverageTouchedCount}`
      : "暂无论文指向";

  return (
    <div
      className={[
        "pm-node",
        "pm-node--problem",
        data.isRoot ? "pm-node--problem--root" : "",
        selected ? "pm-node--selected" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <Handle type="source" id="top" position={Position.Top} className="k-handle" />
      <Handle type="source" id="right" position={Position.Right} className="k-handle" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="k-handle" />
      <Handle type="source" id="left" position={Position.Left} className="k-handle" />
      <div className="pm-node__badge">{badge}</div>
      <div className="pm-node__title">{data.title || "未命名问题"}</div>
      {data.description && <div className="pm-node__description">{data.description}</div>}
    </div>
  );
}
