import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ConversationMode, NodeSource, SessionSource } from "../../entities/context/types";
import { CONVERSATION_MODE_LABELS } from "../../entities/context/types";
import { listSessions } from "../conversations/api";
import * as api from "./api";

interface Props {
  sessionId: string;
  nodeId: string;
  compact?: boolean;
}

function emptySession(sessionId: string): SessionSource {
  return {
    source_session_id: sessionId,
    conversation_mode: "FULL_SESSION",
    last_n_turns: 2,
    selected_message_ids: [],
    order_index: 0,
  };
}

export function ContextPolicyPanel({ sessionId, nodeId, compact = false }: Props) {
  const qc = useQueryClient();
  const [includeSummary, setIncludeSummary] = useState(false);
  const [maxTokens, setMaxTokens] = useState<string>("");
  const [sources, setSources] = useState<NodeSource[]>([]);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewMeta, setPreviewMeta] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [addNodeId, setAddNodeId] = useState("");
  const [open, setOpen] = useState(!compact);

  const policyQuery = useQuery({
    queryKey: ["sessions", sessionId, "context-policy"],
    queryFn: () => api.getContextPolicy(sessionId),
    enabled: Boolean(sessionId),
  });
  const candidatesQuery = useQuery({
    queryKey: ["sessions", sessionId, "context-candidates"],
    queryFn: () => api.getContextCandidates(sessionId),
    enabled: Boolean(sessionId),
  });
  const ownSessionsQuery = useQuery({
    queryKey: ["nodes", nodeId, "sessions"],
    queryFn: () => listSessions(nodeId),
  });

  useEffect(() => {
    const policy = policyQuery.data;
    if (!policy) return;
    setIncludeSummary(policy.include_current_node_summary);
    setMaxTokens(policy.max_context_tokens ? String(policy.max_context_tokens) : "");
    setSources(policy.sources.map((s) => ({ ...s, sessions: s.sessions.map((x) => ({ ...x })) })));
    setError(null);
    setPreviewText(null);
  }, [policyQuery.data, sessionId]);

  const nonAncestorSelected = useMemo(
    () => sources.filter((s) => !s.is_same_node && !s.is_ancestor).length,
    [sources],
  );

  const availableToAdd = useMemo(() => {
    const selected = new Set(sources.map((s) => s.source_node_id));
    const ancestors = (candidatesQuery.data?.ancestors ?? []).filter((n) => !selected.has(n.id));
    const nonAncestors = (candidatesQuery.data?.non_ancestors ?? []).filter((n) => !selected.has(n.id));
    return { ancestors, nonAncestors };
  }, [candidatesQuery.data, sources]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.putContextPolicy(sessionId, {
        include_current_node_summary: includeSummary,
        max_context_tokens: maxTokens.trim() ? Number(maxTokens) : null,
        sources: sources.map((s, index) => ({
          source_node_id: s.source_node_id,
          include_summary: s.is_same_node ? false : s.include_summary,
          order_index: index,
          sessions: s.sessions.map((sess, sidx) => ({
            source_session_id: sess.source_session_id,
            conversation_mode: sess.conversation_mode,
            last_n_turns: sess.conversation_mode === "LAST_N_TURNS" ? sess.last_n_turns ?? 2 : null,
            selected_message_ids:
              sess.conversation_mode === "SELECTED_MESSAGES" ? sess.selected_message_ids ?? [] : [],
            order_index: sidx,
          })),
        })),
      }),
    onSuccess: async () => {
      setError(null);
      await qc.invalidateQueries({ queryKey: ["sessions", sessionId, "context-policy"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const previewMutation = useMutation({
    mutationFn: async () => {
      await saveMutation.mutateAsync();
      return api.previewContext(sessionId, { new_user_message: "（预览用示例问题）" });
    },
    onSuccess: (data) => {
      setPreviewText(`${data.rendered_system_prompt}\n\n${data.rendered_context}`);
      setPreviewMeta(
        `约 ${data.estimated_input_tokens} tokens` + (data.truncated ? " · 已因长度裁剪" : ""),
      );
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const titleOf = (id: string) => {
    const all = [
      ...(candidatesQuery.data?.ancestors ?? []),
      ...(candidatesQuery.data?.non_ancestors ?? []),
    ];
    if (id === nodeId) return "本节点";
    return all.find((n) => n.id === id)?.title ?? id.slice(0, 8);
  };

  const addSource = async (sourceNodeId: string, kind: "same" | "ancestor" | "non") => {
    if (kind === "non" && nonAncestorSelected >= 2) {
      setError("非祖先节点最多只能借 2 个");
      return;
    }
    let sessions: SessionSource[] = [];
    if (kind === "same") {
      const list = ownSessionsQuery.data ?? (await listSessions(nodeId));
      const other = list.filter((s) => s.id !== sessionId);
      if (other.length === 0) {
        setError("没有可借用的其他会话，请先再创建一场会话");
        return;
      }
      sessions = [emptySession(other[0].id)];
    }
    setSources((prev) => [
      ...prev,
      {
        source_node_id: sourceNodeId,
        include_summary: kind !== "same",
        order_index: prev.length,
        is_same_node: kind === "same",
        is_ancestor: kind === "ancestor",
        sessions,
      },
    ]);
    setAddNodeId("");
    setError(null);
  };

  return (
    <section className={`inspector__slot ${compact ? "context-panel--compact" : ""}`}>
      <div className="inspector__slot-head">
        <h3>上下文继承</h3>
        <button type="button" className="btn btn--ghost" onClick={() => setOpen((v) => !v)}>
          {open ? "收起" : "展开"}
        </button>
      </div>
      {!open ? (
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          本场对话专属设置。当前会话历史始终带上。
        </p>
      ) : (
        <>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            归属当前这场对话。当前会话历史会自动带上，无需勾选。
          </p>

          <div className="context-always-on">当前会话历史：始终继承</div>

          <label className="check-row">
            <input
              type="checkbox"
              checked={includeSummary}
              onChange={(e) => setIncludeSummary(e.target.checked)}
            />
            本节点摘要
          </label>
          <label>
            最大 token（可选）
            <input
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              placeholder="例如 4000，留空表示不裁剪"
            />
          </label>

          <div className="context-add">
            <button type="button" className="btn btn--ghost" onClick={() => void addSource(nodeId, "same")}>
              + 本节点其他会话
            </button>
          </div>

          <label>
            添加借用节点
            <select value={addNodeId} onChange={(e) => setAddNodeId(e.target.value)}>
              <option value="">选择节点…</option>
              <optgroup label="前 3 代祖先">
                {availableToAdd.ancestors.map((n) => (
                  <option key={n.id} value={`ancestor:${n.id}`}>
                    {n.title}（第 {n.generation} 代）
                  </option>
                ))}
              </optgroup>
              <optgroup label={`非祖先（还可选 ${Math.max(0, 2 - nonAncestorSelected)} 个）`}>
                {availableToAdd.nonAncestors.map((n) => (
                  <option key={n.id} value={`non:${n.id}`}>
                    {n.title}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!addNodeId}
            onClick={() => {
              const [kind, id] = addNodeId.split(":");
              void addSource(id, kind === "ancestor" ? "ancestor" : "non");
            }}
          >
            添加该节点
          </button>

          <ul className="context-source-list">
            {sources.map((source, sourceIndex) => (
              <li key={`${source.source_node_id}-${sourceIndex}`}>
                <div className="context-source-list__head">
                  <strong>
                    {titleOf(source.source_node_id)}
                    {source.is_same_node ? " · 其他会话" : source.is_ancestor ? " · 祖先" : " · 非祖先"}
                  </strong>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => setSources((prev) => prev.filter((_, i) => i !== sourceIndex))}
                  >
                    移除
                  </button>
                </div>

                {!source.is_same_node && (
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={source.include_summary}
                      onChange={(e) =>
                        setSources((prev) =>
                          prev.map((s, i) =>
                            i === sourceIndex ? { ...s, include_summary: e.target.checked } : s,
                          ),
                        )
                      }
                    />
                    借用摘要
                  </label>
                )}

                {source.sessions.map((sess, sessIndex) => (
                  <div key={sessIndex} className="context-session-block">
                    <label>
                      会话
                      <SessionPicker
                        nodeId={source.source_node_id}
                        value={sess.source_session_id}
                        excludeSessionId={source.is_same_node ? sessionId : null}
                        onChange={(nextId) =>
                          setSources((prev) =>
                            prev.map((s, i) =>
                              i === sourceIndex
                                ? {
                                    ...s,
                                    sessions: s.sessions.map((x, j) =>
                                      j === sessIndex ? { ...x, source_session_id: nextId } : x,
                                    ),
                                  }
                                : s,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      借用方式
                      <select
                        value={sess.conversation_mode}
                        onChange={(e) =>
                          setSources((prev) =>
                            prev.map((s, i) =>
                              i === sourceIndex
                                ? {
                                    ...s,
                                    sessions: s.sessions.map((x, j) =>
                                      j === sessIndex
                                        ? { ...x, conversation_mode: e.target.value as ConversationMode }
                                        : x,
                                    ),
                                  }
                                : s,
                            ),
                          )
                        }
                      >
                        {Object.entries(CONVERSATION_MODE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                    {sess.conversation_mode === "LAST_N_TURNS" && (
                      <label>
                        N 轮
                        <input
                          type="number"
                          min={1}
                          value={sess.last_n_turns ?? 2}
                          onChange={(e) =>
                            setSources((prev) =>
                              prev.map((s, i) =>
                                i === sourceIndex
                                  ? {
                                      ...s,
                                      sessions: s.sessions.map((x, j) =>
                                        j === sessIndex
                                          ? { ...x, last_n_turns: Number(e.target.value) }
                                          : x,
                                      ),
                                    }
                                  : s,
                              ),
                            )
                          }
                        />
                      </label>
                    )}
                    {sess.conversation_mode === "SELECTED_MESSAGES" && (
                      <label>
                        消息 ID（逗号分隔）
                        <input
                          value={(sess.selected_message_ids ?? []).join(",")}
                          onChange={(e) =>
                            setSources((prev) =>
                              prev.map((s, i) =>
                                i === sourceIndex
                                  ? {
                                      ...s,
                                      sessions: s.sessions.map((x, j) =>
                                        j === sessIndex
                                          ? {
                                              ...x,
                                              selected_message_ids: e.target.value
                                                .split(",")
                                                .map((t) => t.trim())
                                                .filter(Boolean),
                                            }
                                          : x,
                                      ),
                                    }
                                  : s,
                              ),
                            )
                          }
                        />
                      </label>
                    )}
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() =>
                        setSources((prev) =>
                          prev.map((s, i) =>
                            i === sourceIndex
                              ? { ...s, sessions: s.sessions.filter((_, j) => j !== sessIndex) }
                              : s,
                          ),
                        )
                      }
                    >
                      移除该会话
                    </button>
                  </div>
                ))}

                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={async () => {
                    const list = await listSessions(source.source_node_id);
                    const first = list.find((s) => s.id !== sessionId) ?? list[0];
                    if (!first) {
                      setError("该节点还没有可借用的会话");
                      return;
                    }
                    setSources((prev) =>
                      prev.map((s, i) =>
                        i === sourceIndex
                          ? { ...s, sessions: [...s.sessions, emptySession(first.id)] }
                          : s,
                      ),
                    );
                  }}
                >
                  + 再借一场会话
                </button>
              </li>
            ))}
          </ul>

          {error && <p className="error-text">{error}</p>}

          <div className="inspector__actions">
            <button
              type="button"
              className="btn"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              保存设置
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={previewMutation.isPending}
              onClick={() => previewMutation.mutate()}
            >
              预览上下文
            </button>
          </div>

          {previewText && (
            <div className="context-preview">
              <div className="inspector__slot-head">
                <h3>预览</h3>
                {previewMeta && <span className="slot-badge">{previewMeta}</span>}
              </div>
              <pre>{previewText}</pre>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function SessionPicker({
  nodeId,
  value,
  onChange,
  excludeSessionId,
}: {
  nodeId: string;
  value: string;
  onChange: (id: string) => void;
  excludeSessionId?: string | null;
}) {
  const query = useQuery({
    queryKey: ["nodes", nodeId, "sessions"],
    queryFn: () => listSessions(nodeId),
  });
  const options = (query.data ?? []).filter((s) => s.id !== excludeSessionId);

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((s) => (
        <option key={s.id} value={s.id}>
          {s.title}
        </option>
      ))}
    </select>
  );
}
