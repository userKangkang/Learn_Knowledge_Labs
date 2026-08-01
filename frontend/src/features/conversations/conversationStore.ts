import { create } from "zustand";

interface ConversationUiState {
  drawerOpen: boolean;
  activeNodeId: string | null;
  activeSessionId: string | null;
  openDrawer: (nodeId: string, sessionId?: string | null) => void;
  closeDrawer: () => void;
  setActiveSessionId: (sessionId: string | null) => void;
}

export const useConversationStore = create<ConversationUiState>((set) => ({
  drawerOpen: false,
  activeNodeId: null,
  activeSessionId: null,
  openDrawer: (nodeId, sessionId = null) =>
    set({ drawerOpen: true, activeNodeId: nodeId, activeSessionId: sessionId }),
  closeDrawer: () => set({ drawerOpen: false }),
  setActiveSessionId: (sessionId) => set({ activeSessionId: sessionId }),
}));
