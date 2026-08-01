import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { confirmDialog } from "../../shared/ui/dialogStore";
import * as api from "./api";
import { useConversationStore } from "./conversationStore";

interface Props {
  nodeId: string;
}

export function SessionList({ nodeId }: Props) {
  const qc = useQueryClient();
  const openDrawer = useConversationStore((s) => s.openDrawer);
  const activeSessionId = useConversationStore((s) => s.activeSessionId);

  const sessionsQuery = useQuery({
    queryKey: ["nodes", nodeId, "sessions"],
    queryFn: () => api.listSessions(nodeId),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createSession(nodeId),
    onSuccess: async (session) => {
      await qc.invalidateQueries({ queryKey: ["nodes", nodeId, "sessions"] });
      openDrawer(nodeId, session.id);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => api.deleteSession(sessionId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["nodes", nodeId, "sessions"] });
    },
  });

  return (
    <section className="inspector__slot">
      <div className="inspector__slot-head">
        <h3>会话</h3>
        <button type="button" className="btn btn--ghost" onClick={() => createMutation.mutate()}>
          新建
        </button>
      </div>
      {(sessionsQuery.data?.length ?? 0) === 0 && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          还没有会话。可新建后打开对话面板写入消息。
        </p>
      )}
      <ul className="session-list">
        {sessionsQuery.data?.map((session) => (
          <li key={session.id} className={session.id === activeSessionId ? "session-list__item--active" : ""}>
            <button
              type="button"
              className="session-list__open"
              onClick={() => openDrawer(nodeId, session.id)}
            >
              {session.title}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={async () => {
                const ok = await confirmDialog({
                  title: "删除会话",
                  description: `确认删除会话「${session.title}」？其中的消息将一并软删除。`,
                  confirmLabel: "删除",
                  tone: "danger",
                });
                if (ok) deleteMutation.mutate(session.id);
              }}
            >
              删
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="btn"
        onClick={async () => {
          if ((sessionsQuery.data?.length ?? 0) === 0) {
            createMutation.mutate();
            return;
          }
          openDrawer(nodeId, sessionsQuery.data?.[0]?.id ?? null);
        }}
      >
        打开对话
      </button>
    </section>
  );
}
