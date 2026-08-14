import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

export type PaperFlowNode = Node<
  {
    title: string;
    cardCount: number;
    cardTitles: string[];
  },
  "paper"
>;

export function PaperNodeView({ data, selected }: NodeProps<PaperFlowNode>) {
  return (
    <div
      className={["pm-node", "pm-node--paper", selected ? "pm-node--selected" : ""]
        .filter(Boolean)
        .join(" ")}
      title={data.cardTitles.length ? `问题卡：\n${data.cardTitles.join("\n")}` : "尚未创建问题卡"}
    >
      <Handle type="source" id="top" position={Position.Top} className="k-handle" />
      <Handle type="source" id="right" position={Position.Right} className="k-handle" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="k-handle" />
      <Handle type="source" id="left" position={Position.Left} className="k-handle" />
      <div className="pm-node__badge pm-node__badge--paper">论文</div>
      <div className="pm-node__title">{data.title || "未命名论文"}</div>
      <div className="pm-node__description">{data.cardCount ? `问题卡 ${data.cardCount} 张` : "暂无问题卡"}</div>
    </div>
  );
}
