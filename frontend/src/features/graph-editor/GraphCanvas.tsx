import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
  type OnNodeDrag,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import { EdgeInspector } from "./EdgeInspector";
import { EdgeTypeDialog } from "./EdgeTypeDialog";
import { EmptyCanvasHint } from "./EmptyCanvasHint";
import { pickHandlesForNodes } from "./edgeRouting";
import { KnowledgeNodeView, type KnowledgeFlowNode } from "./KnowledgeNode";
import { TypedEdge, type KnowledgeFlowEdge } from "./TypedEdge";
import { useEditorStore } from "./editorStore";
import { ChatDrawer } from "../conversations/ChatDrawer";
import { useConversationStore } from "../conversations/conversationStore";
import { NodeInspector } from "../node-inspector/NodeInspector";
import type { EdgeType } from "../../entities/edge/types";
import type { KnowledgeNode } from "../../entities/node/types";
import { ApiError } from "../../shared/api/client";

const nodeTypes = { knowledge: KnowledgeNodeView };
const edgeTypes = { typed: TypedEdge };

const DEFAULT_STRUCTURAL_EDGE: EdgeType = "PART_OF";
const CHILD_OFFSET = { x: 36, y: 150 };
const SIBLING_OFFSET = { x: 230, y: 0 };

function toFlowNodes(nodes: KnowledgeNode[], selectedNodeId: string | null = null): KnowledgeFlowNode[] {
  return nodes.map((node) => ({
    id: node.id,
    type: "knowledge",
    position: { x: node.position_x, y: node.position_y },
    selected: node.id === selectedNodeId,
    data: {
      title: node.title,
      nodeType: node.node_type,
      summaryPreview: node.summary_preview ?? null,
    },
  }));
}

function isGraphHotkeyBlocked(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(
    target.closest(
      'input, textarea, select, [contenteditable="true"], .modal, [role="dialog"], .chat-drawer, .inspector, .topbar',
    ),
  );
}

function toFlowEdges(edges: Awaited<ReturnType<typeof api.listEdges>>): KnowledgeFlowEdge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    type: "typed",
    markerEnd: { type: MarkerType.ArrowClosed },
    data: { edgeType: edge.type, customLabel: edge.custom_label },
  }));
}

/** Attach handles by current geometry so parent→child is not visually locked LTR. */
function withRoutedHandles(
  flowEdges: KnowledgeFlowEdge[],
  flowNodes: KnowledgeFlowNode[],
): KnowledgeFlowEdge[] {
  const byId = new Map(flowNodes.map((n) => [n.id, n]));
  return flowEdges.map((edge) => {
    const sourceNode = byId.get(edge.source);
    const targetNode = byId.get(edge.target);
    if (!sourceNode || !targetNode) return edge;
    const routed = pickHandlesForNodes(sourceNode, targetNode);
    return {
      ...edge,
      sourceHandle: routed.sourceHandle,
      targetHandle: routed.targetHandle,
    };
  });
}

interface Props {
  graphId: string;
}

function GraphCanvasInner({ graphId }: Props) {
  const qc = useQueryClient();
  const [nodes, setNodes, onNodesChange] = useNodesState<KnowledgeFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<KnowledgeFlowEdge>([]);
  const positionTimers = useRef<Record<string, number>>({});
  const [edgeDialogMode, setEdgeDialogMode] = useState<"create" | "edit" | null>(null);

  const selectedNodeId = useEditorStore((s) => s.selectedNodeId);
  const selectedEdgeId = useEditorStore((s) => s.selectedEdgeId);
  const pendingConnection = useEditorStore((s) => s.pendingConnection);
  const notice = useEditorStore((s) => s.notice);
  const addNodeNonce = useEditorStore((s) => s.addNodeNonce);
  const editEdgeNonce = useEditorStore((s) => s.editEdgeNonce);
  const deleteEdgeNonce = useEditorStore((s) => s.deleteEdgeNonce);
  const setSelectedNodeId = useEditorStore((s) => s.setSelectedNodeId);
  const setSelectedEdgeId = useEditorStore((s) => s.setSelectedEdgeId);
  const setPendingConnection = useEditorStore((s) => s.setPendingConnection);
  const setSaveStatus = useEditorStore((s) => s.setSaveStatus);
  const setNotice = useEditorStore((s) => s.setNotice);
  const chatDrawerOpen = useConversationStore((s) => s.drawerOpen);
  const prevAddNonce = useRef(0);
  const prevEditNonce = useRef(0);
  const prevDeleteNonce = useRef(0);

  const nodesQuery = useQuery({
    queryKey: ["graphs", graphId, "nodes"],
    queryFn: () => api.listNodes(graphId),
  });
  const edgesQuery = useQuery({
    queryKey: ["graphs", graphId, "edges"],
    queryFn: () => api.listEdges(graphId),
  });

  useEffect(() => {
    if (nodesQuery.data) setNodes(toFlowNodes(nodesQuery.data, selectedNodeId));
  }, [nodesQuery.data, selectedNodeId, setNodes]);

  useEffect(() => {
    if (!edgesQuery.data) return;
    const routed = withRoutedHandles(toFlowEdges(edgesQuery.data), nodes);
    setEdges((prev) => {
      const selectedIds = new Set(prev.filter((e) => e.selected).map((e) => e.id));
      if (selectedEdgeId) selectedIds.add(selectedEdgeId);
      const next = routed.map((edge) => ({ ...edge, selected: selectedIds.has(edge.id) }));
      const unchanged =
        prev.length === next.length &&
        next.every(
          (edge, i) =>
            prev[i]?.id === edge.id &&
            prev[i]?.source === edge.source &&
            prev[i]?.target === edge.target &&
            prev[i]?.sourceHandle === edge.sourceHandle &&
            prev[i]?.targetHandle === edge.targetHandle &&
            prev[i]?.selected === edge.selected &&
            prev[i]?.data?.edgeType === edge.data?.edgeType &&
            prev[i]?.data?.customLabel === edge.data?.customLabel,
        );
      return unchanged ? prev : next;
    });
  }, [edgesQuery.data, nodes, selectedEdgeId, setEdges]);

  const invalidateGraph = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["graphs", graphId, "nodes"] }),
      qc.invalidateQueries({ queryKey: ["graphs", graphId, "edges"] }),
    ]);
  }, [graphId, qc]);

  const creatingRelatedRef = useRef(false);

  const createNodeMutation = useMutation({
    mutationFn: () =>
      api.createNode(graphId, {
        title: "新节点",
        node_type: "CONCEPT",
        position_x: 120 + Math.random() * 240,
        position_y: 120 + Math.random() * 180,
      }),
    onSuccess: async (node) => {
      setSaveStatus("saved");
      setSelectedNodeId(node.id);
      await invalidateGraph();
    },
  });

  const createRelatedNode = useCallback(
    async (mode: "child" | "sibling") => {
      if (!selectedNodeId || creatingRelatedRef.current || edgeDialogMode !== null) return;
      const current = nodesQuery.data?.find((n) => n.id === selectedNodeId);
      if (!current) return;

      const graphEdges = edgesQuery.data ?? [];
      creatingRelatedRef.current = true;
      setSaveStatus("saving");
      try {
        let position_x = current.position_x;
        let position_y = current.position_y;
        let parentEdge: (typeof graphEdges)[number] | null = null;

        if (mode === "child") {
          const childCount = graphEdges.filter((e) => e.source_node_id === current.id).length;
          position_x = current.position_x + CHILD_OFFSET.x + childCount * 28;
          position_y = current.position_y + CHILD_OFFSET.y;
        } else {
          parentEdge =
            graphEdges.find((e) => e.target_node_id === current.id) ?? null;
          const siblingIndex = parentEdge
            ? graphEdges.filter((e) => e.source_node_id === parentEdge!.source_node_id).length
            : 0;
          position_x = current.position_x + SIBLING_OFFSET.x;
          position_y = current.position_y + SIBLING_OFFSET.y + siblingIndex * 8;
        }

        const created = await api.createNode(graphId, {
          title: "新节点",
          node_type: current.node_type,
          position_x,
          position_y,
        });

        if (mode === "child") {
          await api.createEdge(graphId, {
            source_node_id: current.id,
            target_node_id: created.id,
            type: DEFAULT_STRUCTURAL_EDGE,
          });
        } else if (parentEdge) {
          await api.createEdge(graphId, {
            source_node_id: parentEdge.source_node_id,
            target_node_id: created.id,
            type: parentEdge.type,
            custom_label: parentEdge.custom_label ?? undefined,
          });
        }

        setSelectedNodeId(created.id);
        setSaveStatus("saved");
        await invalidateGraph();
      } catch (err) {
        setSaveStatus("error");
        setNotice(err instanceof ApiError ? err.message : mode === "child" ? "创建子节点失败" : "创建兄弟节点失败");
      } finally {
        creatingRelatedRef.current = false;
      }
    },
    [
      selectedNodeId,
      edgeDialogMode,
      nodesQuery.data,
      edgesQuery.data,
      graphId,
      invalidateGraph,
      setSaveStatus,
      setSelectedNodeId,
      setNotice,
    ],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isGraphHotkeyBlocked(event.target)) return;
      if (!selectedNodeId || edgeDialogMode !== null) return;

      if (event.key === "Tab" && !event.shiftKey) {
        event.preventDefault();
        void createRelatedNode("child");
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void createRelatedNode("sibling");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedNodeId, edgeDialogMode, createRelatedNode]);

  const updateNodeMutation = useMutation({
    mutationFn: ({ nodeId, ...payload }: { nodeId: string; title: string; node_type: KnowledgeNode["node_type"] }) =>
      api.updateNode(nodeId, payload),
    onSuccess: async () => {
      setSaveStatus("saved");
      await invalidateGraph();
    },
  });

  const deleteNodeMutation = useMutation({
    mutationFn: (nodeId: string) => api.deleteNode(nodeId),
    onSuccess: async () => {
      setSelectedNodeId(null);
      setSaveStatus("saved");
      await invalidateGraph();
    },
  });

  const createEdgeMutation = useMutation({
    mutationFn: (payload: {
      source_node_id: string;
      target_node_id: string;
      type: EdgeType;
      custom_label?: string;
    }) => api.createEdge(graphId, payload),
    onSuccess: async () => {
      setSaveStatus("saved");
      await invalidateGraph();
    },
  });

  const updateEdgeMutation = useMutation({
    mutationFn: ({
      edgeId,
      ...payload
    }: {
      edgeId: string;
      type?: EdgeType;
      custom_label?: string | null;
      reverse?: boolean;
    }) => api.updateEdge(edgeId, payload),
    onSuccess: async () => {
      setSaveStatus("saved");
      await invalidateGraph();
    },
  });

  const deleteEdgeMutation = useMutation({
    mutationFn: (edgeId: string) => api.deleteEdge(edgeId),
    onSuccess: async () => {
      setSelectedEdgeId(null);
      setSaveStatus("saved");
      await invalidateGraph();
    },
  });

  const persistPosition = useCallback(
    (nodeId: string, x: number, y: number) => {
      window.clearTimeout(positionTimers.current[nodeId]);
      setSaveStatus("saving");
      positionTimers.current[nodeId] = window.setTimeout(async () => {
        try {
          await api.updateNodePosition(nodeId, x, y);
          setSaveStatus("saved");
        } catch {
          setSaveStatus("error");
        }
      }, 300);
    },
    [setSaveStatus],
  );

  const onNodeDragStop: OnNodeDrag = useCallback(
    (_event, node) => {
      persistPosition(node.id, node.position.x, node.position.y);
    },
    [persistPosition],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      setPendingConnection({ source: connection.source, target: connection.target });
      setEdgeDialogMode("create");
    },
    [setPendingConnection],
  );

  const selectedNode = useMemo(
    () => nodesQuery.data?.find((n) => n.id === selectedNodeId) ?? null,
    [nodesQuery.data, selectedNodeId],
  );

  const selectedEdge = useMemo(
    () => edgesQuery.data?.find((e) => e.id === selectedEdgeId) ?? null,
    [edgesQuery.data, selectedEdgeId],
  );

  const isEmpty = (nodesQuery.data?.length ?? 0) === 0;

  const openEditEdgeDialog = useCallback(() => {
    if (!selectedEdge) return;
    setEdgeDialogMode("edit");
  }, [selectedEdge]);

  useEffect(() => {
    if (addNodeNonce === prevAddNonce.current) return;
    prevAddNonce.current = addNodeNonce;
    if (addNodeNonce === 0) return;
    setSaveStatus("saving");
    createNodeMutation.mutate();
    // Intentionally depend only on the toolbar nonce.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addNodeNonce]);

  useEffect(() => {
    if (editEdgeNonce === prevEditNonce.current) return;
    prevEditNonce.current = editEdgeNonce;
    if (editEdgeNonce === 0) return;
    openEditEdgeDialog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editEdgeNonce]);

  useEffect(() => {
    if (deleteEdgeNonce === prevDeleteNonce.current) return;
    prevDeleteNonce.current = deleteEdgeNonce;
    if (deleteEdgeNonce === 0 || !selectedEdgeId) return;
    setSaveStatus("saving");
    deleteEdgeMutation.mutate(selectedEdgeId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deleteEdgeNonce]);

  return (
    <div className="editor-shell">
      <div className={`editor-main${chatDrawerOpen ? " editor-main--with-chat" : ""}`}>
        {chatDrawerOpen && <ChatDrawer graphId={graphId} />}
        <div className="canvas-wrap">
          {isEmpty && <EmptyCanvasHint />}
          <ReactFlow<KnowledgeFlowNode, KnowledgeFlowEdge>
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={(_e, node) => setSelectedNodeId(node.id)}
            onEdgeClick={(_e, edge) => setSelectedEdgeId(edge.id)}
            onPaneClick={() => {
              setSelectedNodeId(null);
              setSelectedEdgeId(null);
            }}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            connectionMode={ConnectionMode.Loose}
            fitView
            deleteKeyCode={null}
          >
            <Background gap={18} size={1} />
            <MiniMap />
            <Controls />
          </ReactFlow>
        </div>

        {selectedEdge ? (
          <EdgeInspector
            edge={selectedEdge}
            sourceTitle={nodesQuery.data?.find((n) => n.id === selectedEdge.source_node_id)?.title}
            targetTitle={nodesQuery.data?.find((n) => n.id === selectedEdge.target_node_id)?.title}
            onClose={() => setSelectedEdgeId(null)}
            onChangeType={openEditEdgeDialog}
            onReverse={async () => {
              setSaveStatus("saving");
              try {
                await updateEdgeMutation.mutateAsync({ edgeId: selectedEdge.id, reverse: true });
              } catch (err) {
                setSaveStatus("error");
                setNotice(err instanceof ApiError ? err.message : "反转方向失败");
              }
            }}
            onDelete={async () => {
              setSaveStatus("saving");
              await deleteEdgeMutation.mutateAsync(selectedEdge.id);
            }}
          />
        ) : (
          <NodeInspector
            node={selectedNode}
            onClose={() => setSelectedNodeId(null)}
            onSave={async (payload) => {
              if (!selectedNode) return;
              setSaveStatus("saving");
              await updateNodeMutation.mutateAsync({ nodeId: selectedNode.id, ...payload });
            }}
            onDelete={async () => {
              if (!selectedNode) return;
              setSaveStatus("saving");
              await deleteNodeMutation.mutateAsync(selectedNode.id);
            }}
          />
        )}
      </div>

      <EdgeTypeDialog
        open={edgeDialogMode !== null}
        mode={edgeDialogMode ?? "create"}
        initialType={edgeDialogMode === "edit" ? (selectedEdge?.type ?? "PREREQUISITE_OF") : "PREREQUISITE_OF"}
        initialCustomLabel={edgeDialogMode === "edit" ? (selectedEdge?.custom_label ?? "") : ""}
        onCancel={() => {
          setEdgeDialogMode(null);
          setPendingConnection(null);
        }}
        onConfirm={async (type, customLabel) => {
          const mode = edgeDialogMode;
          setEdgeDialogMode(null);
          setSaveStatus("saving");
          try {
            if (mode === "create") {
              if (!pendingConnection) return;
              await createEdgeMutation.mutateAsync({
                source_node_id: pendingConnection.source,
                target_node_id: pendingConnection.target,
                type,
                custom_label: customLabel,
              });
            } else if (mode === "edit") {
              if (!selectedEdge) return;
              await updateEdgeMutation.mutateAsync({
                edgeId: selectedEdge.id,
                type,
                custom_label: type === "CUSTOM" ? customLabel ?? null : null,
              });
            }
          } catch (err) {
            setSaveStatus("error");
            setNotice(err instanceof ApiError ? err.message : mode === "edit" ? "更新边失败" : "创建边失败");
          } finally {
            setPendingConnection(null);
          }
        }}
      />

      {notice && (
        <div className="toast" onClick={() => setNotice(null)} role="status">
          {notice}
        </div>
      )}
    </div>
  );
}

export function GraphCanvas({ graphId }: Props) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner graphId={graphId} />
    </ReactFlowProvider>
  );
}
