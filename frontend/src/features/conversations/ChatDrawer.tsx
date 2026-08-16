import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ConversationBranch } from "../../entities/branch/types";
import type { ChatMessage, MessageAttachment } from "../../entities/message/types";
import { listNodes } from "../graph-editor/api";
import { useEditorStore } from "../graph-editor/editorStore";
import { ContextPolicyPanel } from "../context-policy/ContextPolicyPanel";
import { promptDialog } from "../../shared/ui/dialogStore";
import * as api from "./api";
import { useConversationStore } from "./conversationStore";
import { TempAskPanel } from "./TempAskPanel";

interface Props {
  graphId: string;
}

export function ChatDrawer({ graphId }: Props) {
  const qc = useQueryClient();
  const drawerOpen = useConversationStore((s) => s.drawerOpen);
  const activeNodeId = useConversationStore((s) => s.activeNodeId);
  const activeSessionId = useConversationStore((s) => s.activeSessionId);
  const closeDrawer = useConversationStore((s) => s.closeDrawer);
  const openDrawer = useConversationStore((s) => s.openDrawer);
  const setActiveSessionId = useConversationStore((s) => s.setActiveSessionId);
  const selectedNodeId = useEditorStore((s) => s.selectedNodeId);

  const [content, setContent] = useState("");
  const [textModel, setTextModel] = useState<string>("");
  const [webSearch, setWebSearch] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<MessageAttachment[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [liveAssistant, setLiveAssistant] = useState<{ id: string; content: string } | null>(null);
  const [tempAsk, setTempAsk] = useState<{
    anchor: ChatMessage;
    branch?: ConversationBranch | null;
  } | null>(null);
  const [expandedBranchAnchors, setExpandedBranchAnchors] = useState<Record<string, boolean>>({});
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const nodesQuery = useQuery({
    queryKey: ["graphs", graphId, "nodes"],
    queryFn: () => listNodes(graphId),
    enabled: drawerOpen && Boolean(graphId),
  });

  const llmSettingsQuery = useQuery({
    queryKey: ["llm", "settings"],
    queryFn: api.getLlmSettings,
    enabled: drawerOpen,
  });

  const sessionsQuery = useQuery({
    queryKey: ["nodes", activeNodeId, "sessions"],
    queryFn: () => {
      if (!activeNodeId) throw new Error("缺少节点");
      return api.listSessions(activeNodeId);
    },
    enabled: drawerOpen && Boolean(activeNodeId),
  });

  useEffect(() => {
    if (!drawerOpen || !activeNodeId) return;
    if (activeSessionId) return;
    const first = sessionsQuery.data?.[0];
    if (first) setActiveSessionId(first.id);
  }, [drawerOpen, activeNodeId, activeSessionId, sessionsQuery.data, setActiveSessionId]);

  useEffect(() => {
    abortRef.current?.abort();
    setLiveAssistant(null);
    setError(null);
    setStatusNote(null);
    setPendingFiles([]);
    setEditingId(null);
    setStreaming(false);
  }, [activeNodeId]);

  useEffect(() => {
    const settings = llmSettingsQuery.data;
    if (!settings || textModel) return;
    if (settings.default_text_provider === "openai") setTextModel(settings.openai_model);
    else if (settings.default_text_provider === "kimi") setTextModel(settings.kimi_model);
    else setTextModel(settings.model);
  }, [llmSettingsQuery.data, textModel]);

  const messagesQuery = useQuery({
    queryKey: ["sessions", activeSessionId, "messages"],
    queryFn: () => {
      if (!activeSessionId) throw new Error("缺少会话");
      return api.listMessages(activeSessionId);
    },
    enabled: drawerOpen && Boolean(activeSessionId),
  });

  const branchesQuery = useQuery({
    queryKey: ["sessions", activeSessionId, "branches"],
    queryFn: () => {
      if (!activeSessionId) throw new Error("缺少会话");
      return api.listBranches(activeSessionId);
    },
    enabled: drawerOpen && Boolean(activeSessionId),
  });

  const invalidateMessages = async () => {
    if (!activeSessionId) return;
    await qc.invalidateQueries({ queryKey: ["sessions", activeSessionId, "messages"] });
    if (activeNodeId) {
      await qc.invalidateQueries({ queryKey: ["nodes", activeNodeId, "sessions"] });
    }
  };

  const updateMutation = useMutation({
    mutationFn: () => api.updateMessage(editingId!, editDraft),
    onSuccess: async () => {
      setEditingId(null);
      setEditDraft("");
      await invalidateMessages();
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (messageId: string) => api.deleteMessage(messageId),
    onSuccess: async () => {
      await invalidateMessages();
    },
  });

  const renameMutation = useMutation({
    mutationFn: (title: string) => api.updateSession(activeSessionId!, title),
    onSuccess: async () => {
      if (activeNodeId) {
        await qc.invalidateQueries({ queryKey: ["nodes", activeNodeId, "sessions"] });
      }
    },
  });

  const handleStreamEvents = (event: string, data: unknown) => {
    const payload = data as Record<string, unknown>;
    if (event === "request_created") {
      requestIdRef.current = String(payload.request_id ?? "");
      setLiveAssistant({ id: String(payload.assistant_message_id ?? ""), content: "" });
      const model = String(payload.model ?? "");
      if (payload.file_mode) {
        setStatusNote(`Kimi 解析附件中（${model}）…`);
      } else if (payload.web_search) {
        setStatusNote(`联网中（${model}）…`);
      } else {
        setStatusNote(`生成中（${String(payload.provider ?? "")}/${model}）…`);
      }
    } else if (event === "status") {
      setStatusNote(String(payload.message ?? ""));
    } else if (event === "delta") {
      const delta = String(payload.delta ?? "");
      setLiveAssistant((prev) =>
        prev
          ? { ...prev, content: prev.content + delta }
          : { id: String(payload.assistant_message_id ?? "live"), content: delta },
      );
    } else if (event === "failed") {
      setError(String(payload.error_message ?? "生成失败"));
    } else if (event === "cancelled") {
      setError("已取消生成");
    }
  };

  const runTurn = async (note: string, task: (signal: AbortSignal) => Promise<void>) => {
    if (!activeSessionId || streaming) return;
    setError(null);
    setStatusNote(note);
    setStreaming(true);
    setLiveAssistant(null);
    const controller = new AbortController();
    abortRef.current = controller;
    requestIdRef.current = null;

    try {
      await task(controller.signal);
      await invalidateMessages();
      setLiveAssistant(null);
      setStatusNote(null);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
      await invalidateMessages();
      setLiveAssistant(null);
    } finally {
      setStreaming(false);
      abortRef.current = null;
      requestIdRef.current = null;
    }
  };

  const send = async () => {
    if (!activeSessionId) return;
    const text = content.trim();
    const hasFiles = pendingFiles.length > 0;
    if (!text && !hasFiles) return;

    await runTurn(
      hasFiles
        ? "文件解析：强制 Kimi，将生成详细文字摘要"
        : webSearch
          ? `联网：${textModel} + search`
          : `纯文字：${textModel}`,
      async (signal) => {
        await api.streamMessage(
          activeSessionId,
          {
            content: text,
            attachment_ids: pendingFiles.map((f) => f.id),
            web_search: hasFiles ? false : webSearch,
            text_model: textModel,
          },
          handleStreamEvents,
          signal,
        );
        setContent("");
        setPendingFiles([]);
      },
    );
  };

  const retryLastUser = async () => {
    if (!activeSessionId) return;
    const lastUser = [...(messagesQuery.data ?? [])].reverse().find((m) => m.role === "USER");
    const hasFiles = Boolean(lastUser?.attachments?.length);

    await runTurn(
      hasFiles
        ? "重试文件解析：强制 Kimi"
        : webSearch
          ? `重试联网：${textModel} + search`
          : `重试纯文字：${textModel}`,
      async (signal) => {
        await api.retryStreamMessage(
          activeSessionId,
          {
            web_search: hasFiles ? false : webSearch,
            text_model: textModel,
          },
          handleStreamEvents,
          signal,
        );
      },
    );
  };

  const cancel = async () => {
    const requestId = requestIdRef.current;
    abortRef.current?.abort();
    if (requestId) {
      try {
        await api.cancelLlmRequest(requestId);
      } catch {
        /* ignore */
      }
    }
  };

  const onPickPdf = async (fileList: FileList | null) => {
    if (!activeSessionId || !fileList?.length) return;
    setError(null);
    try {
      const uploaded: MessageAttachment[] = [];
      for (const file of Array.from(fileList)) {
        uploaded.push(await api.uploadAttachment(activeSessionId, file));
      }
      setPendingFiles((prev) => [...prev, ...uploaded]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (!drawerOpen || !activeNodeId) return null;

  const activeSession = sessionsQuery.data?.find((s) => s.id === activeSessionId);
  const messages = messagesQuery.data ?? [];
  const branches = branchesQuery.data ?? [];
  const branchesByAnchor = branches.reduce<Record<string, ConversationBranch[]>>((acc, branch) => {
    (acc[branch.anchor_message_id] ??= []).push(branch);
    return acc;
  }, {});
  const lastUserMessageId = [...messages].reverse().find((m) => m.role === "USER")?.id ?? null;
  const showLive = Boolean(liveAssistant && !messages.some((m) => m.id === liveAssistant.id));
  const chatNode = nodesQuery.data?.find((n) => n.id === activeNodeId);
  const selectedNode = nodesQuery.data?.find((n) => n.id === selectedNodeId);
  const chatNodeTitle = chatNode?.title ?? "未知节点";
  const selectionMismatch = Boolean(selectedNodeId && selectedNodeId !== activeNodeId);

  return (
    <aside className="chat-drawer" aria-label={`节点对话：${chatNodeTitle}`}>
      {tempAsk && activeSessionId && (
        <TempAskPanel
          sessionId={activeSessionId}
          anchor={tempAsk.anchor}
          mainlinePrefix={(() => {
            const prefix: ChatMessage[] = [];
            for (const message of messages) {
              prefix.push(message);
              if (message.id === tempAsk.anchor.id) break;
            }
            return prefix.length > 0 ? prefix : [tempAsk.anchor];
          })()}
          textModel={textModel}
          webSearch={webSearch}
          initialBranch={tempAsk.branch}
          onClose={() => setTempAsk(null)}
          onSaved={async () => {
            await qc.invalidateQueries({ queryKey: ["sessions", activeSessionId, "branches"] });
          }}
        />
      )}
      <div className="chat-drawer__header">
        <div>
          <span className="chat-drawer__eyebrow">节点对话</span>
          <h2 title="对话绑定此节点；点选其它节点只切换右侧编辑">{chatNodeTitle}</h2>
        </div>
        <button type="button" className="btn btn--ghost" onClick={closeDrawer}>
          关闭
        </button>
      </div>

      {selectionMismatch && selectedNode && (
        <div className="chat-drawer__bind-note">
          <p>
            右侧在编辑「{selectedNode.title}」，对话仍属「{chatNodeTitle}」。
          </p>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={streaming}
            onClick={() => openDrawer(selectedNode.id)}
          >
            切换对话
          </button>
        </div>
      )}

      <div className="chat-drawer__sessions">
        <select
          value={activeSessionId ?? ""}
          onChange={(e) => setActiveSessionId(e.target.value || null)}
        >
          {(sessionsQuery.data ?? []).map((session) => (
            <option key={session.id} value={session.id}>
              {session.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={!activeSession}
          onClick={async () => {
            const next = await promptDialog({
              title: "重命名会话",
              label: "会话标题",
              defaultValue: activeSession?.title ?? "",
              confirmLabel: "保存",
            });
            if (!next) return;
            renameMutation.mutate(next);
          }}
        >
          重命名
        </button>
      </div>

      {activeSessionId && (
        <div className="chat-drawer__context">
          <ContextPolicyPanel sessionId={activeSessionId} nodeId={activeNodeId} compact />
        </div>
      )}

      <div className="chat-drawer__messages">
        {!activeSessionId && <p className="muted">请先在侧栏新建会话。</p>}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={
              liveAssistant && message.id === liveAssistant.id
                ? { ...message, content: liveAssistant.content || message.content, status: "STREAMING" }
                : message
            }
            editingId={editingId}
            editDraft={editDraft}
            setEditingId={setEditingId}
            setEditDraft={setEditDraft}
            onSaveEdit={() => updateMutation.mutate()}
            onDelete={() => deleteMutation.mutate(message.id)}
            canRetry={message.role === "USER" && message.id === lastUserMessageId && !streaming}
            onRetry={() => void retryLastUser()}
            canTempAsk={message.role === "ASSISTANT" && message.status !== "STREAMING" && !streaming}
            onTempAsk={() => setTempAsk({ anchor: message })}
            branches={branchesByAnchor[message.id] ?? []}
            branchesExpanded={Boolean(expandedBranchAnchors[message.id])}
            onToggleBranches={() =>
              setExpandedBranchAnchors((prev) => ({ ...prev, [message.id]: !prev[message.id] }))
            }
            onOpenBranch={(branch) => setTempAsk({ anchor: message, branch })}
          />
        ))}
        {showLive && liveAssistant && (
          <MessageBubble
            message={{
              id: liveAssistant.id,
              session_id: activeSessionId!,
              role: "ASSISTANT",
              content: liveAssistant.content || "…",
              status: "STREAMING",
              current_revision: 1,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }}
            editingId={null}
            editDraft=""
            setEditingId={() => undefined}
            setEditDraft={() => undefined}
            onSaveEdit={() => undefined}
            onDelete={() => undefined}
            readOnly
          />
        )}
      </div>

      <div className="chat-drawer__composer">
        {error && <p className="error-text">{error}</p>}
        {statusNote && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{statusNote}</p>}
        {pendingFiles.length > 0 && (
          <>
            <p className="composer-tip">
              本轮将用 Kimi 把附件转成<strong>尽可能详细的文字摘要</strong>；PDF 还会同时发送页面视觉图，供模型识别图表、公式和截图。
              请把指令写短（如「解析这篇」「摘要图中公式」），把本轮主要当作文件解析，而不是同时追问很多开放问题——方便之后切换 DeepSeek。
            </p>
            <ul className="chat-attachments">
              {pendingFiles.map((file) => (
                <li key={file.id}>
                  <span>
                    {file.filename}
                    {file.kind === "image" && <span className="muted"> · 图片</span>}
                    {file.extract_status === "FAILED" && (
                      <span className="error-text"> · 文本提取失败</span>
                    )}
                    {file.extract_status === "SUCCEEDED" && (
                      <span className="muted"> · 已抽 PDF 文本</span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={streaming}
                    onClick={() => setPendingFiles((prev) => prev.filter((f) => f.id !== file.id))}
                  >
                    移除
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <textarea
          rows={2}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={
            pendingFiles.length > 0
              ? "简短指令即可，例如：请详细解析附件"
              : "输入问题；需要读图/扫描件时请添加图片或 PDF"
          }
          disabled={!activeSessionId || streaming}
        />
        <div className="chat-drawer__composer-actions">
          <label className="chat-drawer__model">
            模型
            <select
              value={textModel}
              disabled={streaming || pendingFiles.length > 0 || !llmSettingsQuery.data}
              onChange={(e) => setTextModel(e.target.value)}
              title={pendingFiles.length > 0 ? "有附件时强制 Kimi" : "纯文字模型"}
            >
              {llmSettingsQuery.data && (
                <>
                  <option value={llmSettingsQuery.data.model}>DeepSeek</option>
                  <option value={llmSettingsQuery.data.kimi_model}>Kimi</option>
                  <option value={llmSettingsQuery.data.openai_model}>OpenAI · {llmSettingsQuery.data.openai_model}</option>
                </>
              )}
            </select>
          </label>
          <label className="check-row chat-drawer__web-search">
            <input
              type="checkbox"
              checked={webSearch && pendingFiles.length === 0}
              disabled={
                streaming ||
                pendingFiles.length > 0 ||
                !llmSettingsQuery.data
              }
              onChange={(e) => setWebSearch(e.target.checked)}
            />
            联网
            <span className="muted">（DeepSeek / Kimi / OpenAI）</span>
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf,image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
            multiple
            hidden
            onChange={(e) => void onPickPdf(e.target.files)}
          />
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!activeSessionId || streaming}
            onClick={() => fileInputRef.current?.click()}
          >
            添加文件
          </button>
          {streaming ? (
            <button type="button" className="btn btn--ghost" onClick={() => void cancel()}>
              停止
            </button>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={!activeSessionId || (!content.trim() && pendingFiles.length === 0)}
              onClick={() => void send()}
            >
              发送
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

function MessageBubble({
  message,
  editingId,
  editDraft,
  setEditingId,
  setEditDraft,
  onSaveEdit,
  onDelete,
  canRetry = false,
  onRetry,
  canTempAsk = false,
  onTempAsk,
  branches = [],
  branchesExpanded = false,
  onToggleBranches,
  onOpenBranch,
  readOnly = false,
}: {
  message: ChatMessage;
  editingId: string | null;
  editDraft: string;
  setEditingId: (id: string | null) => void;
  setEditDraft: (v: string) => void;
  onSaveEdit: () => void;
  onDelete: () => void;
  canRetry?: boolean;
  onRetry?: () => void;
  canTempAsk?: boolean;
  onTempAsk?: () => void;
  branches?: ConversationBranch[];
  branchesExpanded?: boolean;
  onToggleBranches?: () => void;
  onOpenBranch?: (branch: ConversationBranch) => void;
  readOnly?: boolean;
}) {
  return (
    <article className={`chat-bubble chat-bubble--${message.role.toLowerCase()}`}>
      <header>
        <strong>
          {message.role === "USER" ? "用户" : message.role === "ASSISTANT" ? "助手" : "系统"}
        </strong>
        {message.status === "EDITED" && <span className="slot-badge">已编辑</span>}
        {message.status === "STREAMING" && <span className="slot-badge">生成中</span>}
        {message.status === "FAILED" && <span className="slot-badge">失败</span>}
        {branches.length > 0 && <span className="slot-badge">旁支 {branches.length}</span>}
        <span className="muted">r{message.current_revision}</span>
      </header>
      {(message.attachments ?? []).length > 0 && (
        <ul className="chat-attachments chat-attachments--inline">
          {(message.attachments ?? []).map((file) => (
            <li key={file.id}>{file.filename}</li>
          ))}
        </ul>
      )}
      {editingId === message.id ? (
        <>
          <textarea value={editDraft} onChange={(e) => setEditDraft(e.target.value)} rows={3} />
          <div className="chat-bubble__actions">
            <button type="button" className="btn" onClick={onSaveEdit}>
              保存修订
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setEditingId(null)}>
              取消
            </button>
          </div>
        </>
      ) : (
        <>
          {message.role === "ASSISTANT" ? (
            <div className="markdown-body">
              <Markdown remarkPlugins={[remarkGfm]}>{message.content || " "}</Markdown>
            </div>
          ) : (
            <p>{message.content}</p>
          )}
          {!readOnly && message.status !== "STREAMING" && (
            <div className="chat-bubble__actions">
              {canTempAsk && onTempAsk && (
                <button type="button" className="btn btn--ghost" onClick={onTempAsk}>
                  临时询问
                </button>
              )}
              {branches.length > 0 && onToggleBranches && (
                <button type="button" className="btn btn--ghost" onClick={onToggleBranches}>
                  {branchesExpanded ? "收起旁支" : `展开旁支 (${branches.length})`}
                </button>
              )}
              {canRetry && onRetry && (
                <button type="button" className="btn btn--ghost" onClick={onRetry}>
                  重试
                </button>
              )}
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  setEditingId(message.id);
                  setEditDraft(message.content);
                }}
              >
                编辑
              </button>
              <button type="button" className="btn btn--ghost" onClick={onDelete}>
                删除
              </button>
            </div>
          )}
          {branchesExpanded && branches.length > 0 && (
            <ul className="branch-list">
              {branches.map((branch) => (
                <li key={branch.id}>
                  <button
                    type="button"
                    className="branch-list__open"
                    onClick={() => onOpenBranch?.(branch)}
                  >
                    <strong>{branch.title || "旁支"}</strong>
                    <span className="muted">{branch.message_count} 条</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </article>
  );
}
