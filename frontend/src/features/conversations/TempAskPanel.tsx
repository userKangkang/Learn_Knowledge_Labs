import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ConversationBranch, TempTurn } from "../../entities/branch/types";
import type { ChatMessage } from "../../entities/message/types";
import type { TextModelChoice } from "../../entities/llm/types";
import * as api from "./api";

interface Props {
  sessionId: string;
  anchor: ChatMessage;
  /** Mainline messages from the start of the session through the anchored assistant reply (inclusive). */
  mainlinePrefix: ChatMessage[];
  textModel: TextModelChoice;
  webSearch: boolean;
  initialBranch?: ConversationBranch | null;
  onClose: () => void;
  onSaved: () => void;
}

type LocalTurn = TempTurn & { id: string };

export function TempAskPanel({
  sessionId,
  anchor,
  mainlinePrefix,
  textModel,
  webSearch,
  initialBranch = null,
  onClose,
  onSaved,
}: Props) {
  const [branch, setBranch] = useState<ConversationBranch | null>(initialBranch);
  const [turns, setTurns] = useState<LocalTurn[]>(() =>
    (initialBranch?.messages ?? []).map((m) => ({
      id: m.id,
      role: m.role === "ASSISTANT" ? "ASSISTANT" : "USER",
      content: m.content,
    })),
  );
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [live, setLive] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef<string | null>(null);
  const mainlineRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = mainlineRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [anchor.id, mainlinePrefix.length]);

  const persisted = Boolean(branch);

  const send = async () => {
    const text = draft.trim();
    if (!text || streaming) return;
    setError(null);
    setDraft("");
    setStreaming(true);
    setLive("");
    const controller = new AbortController();
    abortRef.current = controller;
    requestIdRef.current = null;

    const userTurn: LocalTurn = { id: `local-u-${Date.now()}`, role: "USER", content: text };
    setTurns((prev) => [...prev, userTurn]);

    try {
      if (branch) {
        await api.streamBranchMessage(
          branch.id,
          { content: text, text_model: textModel, web_search: webSearch },
          (event, data) => {
            const payload = data as Record<string, unknown>;
            if (event === "request_created") {
              requestIdRef.current = String(payload.request_id ?? "");
            } else if (event === "delta") {
              setLive((prev) => prev + String(payload.delta ?? ""));
            } else if (event === "failed") {
              setError(String(payload.error_message ?? "生成失败"));
            }
          },
          controller.signal,
        );
        const refreshed = await api.listBranches(sessionId, anchor.id);
        const next = refreshed.find((b) => b.id === branch.id) ?? null;
        if (next) {
          setBranch(next);
          setTurns(
            next.messages.map((m) => ({
              id: m.id,
              role: m.role === "ASSISTANT" ? "ASSISTANT" : "USER",
              content: m.content,
            })),
          );
        }
        onSaved();
      } else {
        const prior = turns.map(({ role, content }) => ({ role, content }));
        let assistantText = "";
        await api.streamEphemeralTempChat(
          sessionId,
          {
            anchor_message_id: anchor.id,
            content: text,
            prior_turns: prior,
            text_model: textModel,
            web_search: webSearch,
          },
          (event, data) => {
            const payload = data as Record<string, unknown>;
            if (event === "request_created") {
              requestIdRef.current = String(payload.request_id ?? "");
            } else if (event === "delta") {
              const delta = String(payload.delta ?? "");
              assistantText += delta;
              setLive((prev) => prev + delta);
            } else if (event === "completed") {
              assistantText = String(payload.content ?? assistantText);
            } else if (event === "failed") {
              setError(String(payload.error_message ?? "生成失败"));
            }
          },
          controller.signal,
        );
        if (assistantText.trim()) {
          setTurns((prev) => [
            ...prev,
            { id: `local-a-${Date.now()}`, role: "ASSISTANT", content: assistantText },
          ]);
        }
      }
      setLive("");
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      requestIdRef.current = null;
    }
  };

  const saveBranch = async () => {
    if (persisted || turns.length === 0 || saving) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.createBranch(sessionId, {
        anchor_message_id: anchor.id,
        turns: turns.map(({ role, content }) => ({ role, content })),
        title: turns.find((t) => t.role === "USER")?.content.slice(0, 40),
      });
      setBranch(created);
      setTurns(
        created.messages.map((m) => ({
          id: m.id,
          role: m.role === "ASSISTANT" ? "ASSISTANT" : "USER",
          content: m.content,
        })),
      );
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const cancel = async () => {
    abortRef.current?.abort();
    if (requestIdRef.current && !String(requestIdRef.current).startsWith("local")) {
      try {
        await api.cancelLlmRequest(requestIdRef.current);
      } catch {
        /* ignore */
      }
    }
  };

  return (
    <div className="temp-ask">
      <div className="temp-ask__header">
        <div>
          <p className="chat-drawer__eyebrow">临时询问</p>
          <h3>{persisted ? branch?.title || "已保存旁支" : "未保存旁支（关闭即丢弃）"}</h3>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            上方为完整主线（至锚定回复）；下方是旁支澄清，不会进入后续主线上下文。
          </p>
        </div>
        <button type="button" className="btn btn--ghost" onClick={onClose} disabled={streaming}>
          关闭
        </button>
      </div>

      <div className="temp-ask__mainline" ref={mainlineRef}>
        <div className="temp-ask__section-label">主线上下文（至锚定回复）</div>
        {mainlinePrefix.map((message) => (
          <div
            key={message.id}
            className={`temp-ask__turn temp-ask__turn--${message.role.toLowerCase()} ${
              message.id === anchor.id ? "temp-ask__turn--anchor" : ""
            }`}
          >
            <header>
              {message.role === "USER" ? "用户" : message.role === "ASSISTANT" ? "助手" : "系统"}
              {message.id === anchor.id ? " · 锚定" : ""}
            </header>
            {message.role === "ASSISTANT" || message.role === "SYSTEM" ? (
              <div className="markdown-body">
                <Markdown remarkPlugins={[remarkGfm]}>{message.content || " "}</Markdown>
              </div>
            ) : (
              <p>{message.content}</p>
            )}
          </div>
        ))}
      </div>

      <div className="temp-ask__messages">
        <div className="temp-ask__section-label">临时旁支</div>
        {turns.length === 0 && !live && (
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            针对上面主线里不顺畅的点提问即可，不必另开节点。
          </p>
        )}
        {turns.map((turn) => (
          <div key={turn.id} className={`temp-ask__turn temp-ask__turn--${turn.role.toLowerCase()}`}>
            <header>{turn.role === "USER" ? "你" : "旁支助手"}</header>
            {turn.role === "ASSISTANT" ? (
              <div className="markdown-body">
                <Markdown remarkPlugins={[remarkGfm]}>{turn.content}</Markdown>
              </div>
            ) : (
              <p>{turn.content}</p>
            )}
          </div>
        ))}
        {live && (
          <div className="temp-ask__turn temp-ask__turn--assistant">
            <header>旁支助手 · 生成中</header>
            <div className="markdown-body">
              <Markdown remarkPlugins={[remarkGfm]}>{live}</Markdown>
            </div>
          </div>
        )}
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="temp-ask__composer">
        <textarea
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="临时澄清问题…"
          disabled={streaming}
        />
        <div className="temp-ask__actions">
          {!persisted && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={streaming || saving || turns.length === 0}
              onClick={() => void saveBranch()}
            >
              {saving ? "保存中…" : "保存为旁支"}
            </button>
          )}
          {streaming ? (
            <button type="button" className="btn btn--ghost" onClick={() => void cancel()}>
              停止
            </button>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={!draft.trim()}
              onClick={() => void send()}
            >
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
