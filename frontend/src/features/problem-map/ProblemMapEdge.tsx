import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import type { ProblemLinkType } from "../../entities/problem-map/types";

export type HierarchyFlowEdge = Edge<{ relationLabel: string }>;
export type PaperCardFlowEdge = Edge<Record<string, never>>;
export type CardLinkFlowEdge = Edge<{ linkType: ProblemLinkType }>;

function edgePath(props: Pick<EdgeProps, "sourceX" | "sourceY" | "targetX" | "targetY" | "sourcePosition" | "targetPosition">) {
  return getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  });
}

export function HierarchyEdge({ id, selected, markerEnd, ...rest }: EdgeProps<HierarchyFlowEdge>) {
  const [path, labelX, labelY] = edgePath(rest);
  const label = rest.data?.relationLabel === "SPECIALIZES_INTO" ? "细分" : rest.data?.relationLabel ?? "";
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ strokeWidth: selected ? 2.5 : 1.6 }} />
      <EdgeLabelRenderer>
        <div
          className={`pm-edge-label ${selected ? "pm-edge-label--selected" : ""}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {label}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export function PaperCardEdge({ id, markerEnd, ...rest }: EdgeProps<PaperCardFlowEdge>) {
  const [path] = edgePath(rest);
  return <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ stroke: "#8290a3", strokeWidth: 1.25 }} />;
}

export function CardLinkEdge({ id, selected, markerEnd, ...rest }: EdgeProps<CardLinkFlowEdge>) {
  const [path, labelX, labelY] = edgePath(rest);
  const linkType = rest.data?.linkType ?? "TOUCHED";
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          strokeWidth: selected ? 2.5 : 1.5,
          strokeDasharray: linkType === "TOUCHED" ? "7 5" : undefined,
          stroke: linkType === "CORE" ? "#1f6f5b" : "#5d6775",
        }}
      />
      <EdgeLabelRenderer>
        <div
          className={`pm-edge-label pm-edge-label--card ${selected ? "pm-edge-label--selected" : ""}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          <small>{linkType === "CORE" ? "核心解决" : "顺带提及"}</small>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
