import { Position, type Node } from "@xyflow/react";

/** Handle ids must match KnowledgeNode (ConnectionMode.Loose dual-role handles). */
export type NodeHandleId = "top" | "right" | "bottom" | "left";

const DEFAULT_NODE_SIZE = { width: 200, height: 120 };

function centerOf(node: Node): { x: number; y: number } {
  const width = node.measured?.width ?? node.width ?? DEFAULT_NODE_SIZE.width;
  const height = node.measured?.height ?? node.height ?? DEFAULT_NODE_SIZE.height;
  return {
    x: node.position.x + width / 2,
    y: node.position.y + height / 2,
  };
}

/**
 * Pick connection sides by relative node centers.
 * Layout can be left/right/above/below — ancestry is still edge source→target only.
 */
export function pickHandlesForNodes(
  sourceNode: Node,
  targetNode: Node,
): { sourceHandle: NodeHandleId; targetHandle: NodeHandleId; sourcePosition: Position; targetPosition: Position } {
  const s = centerOf(sourceNode);
  const t = centerOf(targetNode);
  const dx = t.x - s.x;
  const dy = t.y - s.y;

  if (Math.abs(dx) >= Math.abs(dy)) {
    if (dx >= 0) {
      return {
        sourceHandle: "right",
        targetHandle: "left",
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    }
    return {
      sourceHandle: "left",
      targetHandle: "right",
      sourcePosition: Position.Left,
      targetPosition: Position.Right,
    };
  }

  if (dy >= 0) {
    return {
      sourceHandle: "bottom",
      targetHandle: "top",
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    };
  }

  return {
    sourceHandle: "top",
    targetHandle: "bottom",
    sourcePosition: Position.Top,
    targetPosition: Position.Bottom,
  };
}
