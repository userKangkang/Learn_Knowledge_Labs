import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { confirmDialog } from "../../shared/ui/dialogStore";
import * as api from "./api";

interface Props {
  nodeId: string;
  graphId: string;
}

export function SummaryPanel({ nodeId, graphId }: Props) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editingVersionId, setEditingVersionId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const currentQuery = useQuery({
    queryKey: ["nodes", nodeId, "summary"],
    queryFn: () => api.getCurrentSummary(nodeId),
  });
  const versionsQuery = useQuery({
    queryKey: ["nodes", nodeId, "summary", "versions"],
    queryFn: () => api.listSummaryVersions(nodeId),
  });

  useEffect(() => {
    setDraft(currentQuery.data?.content ?? "");
    setError(null);
    setEditingVersionId(null);
  }, [nodeId, currentQuery.data?.id, currentQuery.data?.content]);

  const invalidate = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["nodes", nodeId, "summary"] }),
      qc.invalidateQueries({ queryKey: ["nodes", nodeId, "summary", "versions"] }),
      qc.invalidateQueries({ queryKey: ["graphs", graphId, "nodes"] }),
    ]);
  };

  const saveMutation = useMutation({
    mutationFn: () => api.createSummary(nodeId, draft),
    onSuccess: async () => {
      setError(null);
      await invalidate();
    },
    onError: (err: Error) => setError(err.message),
  });

  const activateMutation = useMutation({
    mutationFn: (versionId: string) => api.activateSummaryVersion(nodeId, versionId),
    onSuccess: async () => {
      await invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ versionId, content }: { versionId: string; content: string }) =>
      api.updateSummaryVersion(nodeId, versionId, content),
    onSuccess: async () => {
      setEditingVersionId(null);
      setEditDraft("");
      setError(null);
      await invalidate();
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (versionId: string) => api.deleteSummaryVersion(nodeId, versionId),
    onSuccess: async () => {
      setEditingVersionId(null);
      await invalidate();
    },
    onError: (err: Error) => setError(err.message),
  });

  const current = currentQuery.data;

  return (
    <section className="inspector__slot">
      <div className="inspector__slot-head">
        <h3>摘要</h3>
        {current && <span className="slot-badge">v{current.version_number}</span>}
      </div>
      <textarea
        className="summary-draft"
        rows={5}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="写下这个节点的要点摘要，点击确认后保存为新版本。"
      />
      {error && <p className="error-text">{error}</p>}
      <div className="inspector__actions">
        <button
          type="button"
          className="btn"
          disabled={!draft.trim() || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          保存为新版本
        </button>
        {current && (
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!draft.trim() || updateMutation.isPending}
            onClick={() => updateMutation.mutate({ versionId: current.id, content: draft })}
          >
            更新当前版本
          </button>
        )}
      </div>

      <div className="version-list">
        <p className="muted" style={{ margin: "8px 0 4px", fontSize: 13 }}>
          版本列表
        </p>
        {(versionsQuery.data?.length ?? 0) === 0 && (
          <p className="muted" style={{ fontSize: 13, margin: 0 }}>
            暂无版本
          </p>
        )}
        <ul>
          {versionsQuery.data?.map((version) => (
            <li key={version.id} className={version.is_current ? "version-item--current" : ""}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <strong>v{version.version_number}</strong>
                  {version.is_current && <span className="slot-badge">当前</span>}
                </div>
                {editingVersionId === version.id ? (
                  <textarea
                    className="summary-draft"
                    rows={3}
                    value={editDraft}
                    onChange={(e) => setEditDraft(e.target.value)}
                  />
                ) : (
                  <p>{version.content}</p>
                )}
              </div>
              <div className="version-list__actions">
                {editingVersionId === version.id ? (
                  <>
                    <button
                      type="button"
                      className="btn"
                      disabled={!editDraft.trim() || updateMutation.isPending}
                      onClick={() =>
                        updateMutation.mutate({
                          versionId: version.id,
                          content: editDraft,
                        })
                      }
                    >
                      保存
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => {
                        setEditingVersionId(null);
                        setEditDraft("");
                      }}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <>
                    {!version.is_current && (
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => activateMutation.mutate(version.id)}
                      >
                        激活
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => {
                        setEditingVersionId(version.id);
                        setEditDraft(version.content);
                      }}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={async () => {
                        const ok = await confirmDialog({
                          title: "删除摘要版本",
                          description: `确认软删除摘要 v${version.version_number}？删除后默认列表中不再显示。`,
                          confirmLabel: "删除",
                          tone: "danger",
                        });
                        if (ok) deleteMutation.mutate(version.id);
                      }}
                    >
                      删除
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
