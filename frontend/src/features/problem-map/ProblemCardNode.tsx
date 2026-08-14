import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

export type ProblemCardFlowNode = Node<
  {
    title: string;
    qualitativeOverview: string;
    paperTitle: string;
    selectedAsCore: boolean;
  },
  "card"
>;

export function ProblemCardNodeView({ data, selected }: NodeProps<ProblemCardFlowNode>) {
  return (
    <div className={["pm-node", "pm-node--card", selected ? "pm-node--selected" : ""].filter(Boolean).join(" ")}>
      <Handle type="source" id="top" position={Position.Top} className="k-handle" />
      <Handle type="source" id="right" position={Position.Right} className="k-handle" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="k-handle" />
      <Handle type="source" id="left" position={Position.Left} className="k-handle" />
      <div className="pm-node__badge pm-node__badge--card">
        论文问题卡{data.selectedAsCore ? " · 已选为深入问题" : ""}
      </div>
      <div className="pm-node__title">{data.title || "未命名问题卡"}</div>
      <div className={`pm-node__description pm-node__description--card ${data.qualitativeOverview ? "" : "is-empty"}`}>
        {data.qualitativeOverview || "尚未填写定性概述"}
      </div>
      <div className="pm-node__source" title={data.paperTitle}>来源：{data.paperTitle}</div>
    </div>
  );
}
