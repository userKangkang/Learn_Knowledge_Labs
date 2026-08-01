import { apiRequest } from "../../shared/api/client";
import type { KnowledgeEdge, EdgeType } from "../../entities/edge/types";
import type { KnowledgeNode, NodeType } from "../../entities/node/types";

export function listNodes(graphId: string) {
  return apiRequest<KnowledgeNode[]>(`/api/v1/graphs/${graphId}/nodes`);
}

export function createNode(
  graphId: string,
  payload: { title: string; node_type?: NodeType; position_x?: number; position_y?: number },
) {
  return apiRequest<KnowledgeNode>(`/api/v1/graphs/${graphId}/nodes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateNode(nodeId: string, payload: { title?: string; node_type?: NodeType }) {
  return apiRequest<KnowledgeNode>(`/api/v1/nodes/${nodeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateNodePosition(nodeId: string, x: number, y: number) {
  return apiRequest<KnowledgeNode>(`/api/v1/nodes/${nodeId}/position`, {
    method: "PATCH",
    body: JSON.stringify({ x, y }),
  });
}

export function deleteNode(nodeId: string) {
  return apiRequest<void>(`/api/v1/nodes/${nodeId}`, { method: "DELETE" });
}

export function listEdges(graphId: string) {
  return apiRequest<KnowledgeEdge[]>(`/api/v1/graphs/${graphId}/edges`);
}

export function createEdge(
  graphId: string,
  payload: {
    source_node_id: string;
    target_node_id: string;
    type: EdgeType;
    custom_label?: string;
  },
) {
  return apiRequest<KnowledgeEdge>(`/api/v1/graphs/${graphId}/edges`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateEdge(
  edgeId: string,
  payload: { type?: EdgeType; custom_label?: string | null; reverse?: boolean },
) {
  return apiRequest<KnowledgeEdge>(`/api/v1/edges/${edgeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteEdge(edgeId: string) {
  return apiRequest<void>(`/api/v1/edges/${edgeId}`, { method: "DELETE" });
}
