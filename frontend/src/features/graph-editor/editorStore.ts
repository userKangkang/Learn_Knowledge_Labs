import { create } from "zustand";
import type { EdgeType } from "../../entities/edge/types";

interface PendingConnection {
  source: string;
  target: string;
}

interface EditorState {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  pendingConnection: PendingConnection | null;
  saveStatus: "idle" | "saving" | "saved" | "error";
  notice: string | null;
  addNodeNonce: number;
  editEdgeNonce: number;
  deleteEdgeNonce: number;
  setSelectedNodeId: (id: string | null) => void;
  setSelectedEdgeId: (id: string | null) => void;
  setPendingConnection: (pending: PendingConnection | null) => void;
  setSaveStatus: (status: EditorState["saveStatus"]) => void;
  setNotice: (notice: string | null) => void;
  requestAddNode: () => void;
  requestEditSelectedEdge: () => void;
  requestDeleteSelectedEdge: () => void;
}

export type { EdgeType };

export const useEditorStore = create<EditorState>((set) => ({
  selectedNodeId: null,
  selectedEdgeId: null,
  pendingConnection: null,
  saveStatus: "idle",
  notice: null,
  addNodeNonce: 0,
  editEdgeNonce: 0,
  deleteEdgeNonce: 0,
  setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedEdgeId: null }),
  setSelectedEdgeId: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),
  setPendingConnection: (pending) => set({ pendingConnection: pending }),
  setSaveStatus: (saveStatus) => set({ saveStatus }),
  setNotice: (notice) => set({ notice }),
  requestAddNode: () => set((s) => ({ addNodeNonce: s.addNodeNonce + 1 })),
  requestEditSelectedEdge: () => set((s) => ({ editEdgeNonce: s.editEdgeNonce + 1 })),
  requestDeleteSelectedEdge: () => set((s) => ({ deleteEdgeNonce: s.deleteEdgeNonce + 1 })),
}));
