import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import { getEdgeDisplayLabel, type EdgeType } from "../../entities/edge/types";

export type KnowledgeFlowEdge = Edge<{
  edgeType: EdgeType;
  customLabel?: string | null;
}>;

export function TypedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerEnd,
}: EdgeProps<KnowledgeFlowEdge>) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const label = data?.edgeType
    ? getEdgeDisplayLabel(data.edgeType, data.customLabel)
    : "";

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ strokeWidth: selected ? 2.5 : 1.5 }} />
      <EdgeLabelRenderer>
        <div
          className={`k-edge-label ${selected ? "k-edge-label--selected" : ""}`}
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          {label}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
