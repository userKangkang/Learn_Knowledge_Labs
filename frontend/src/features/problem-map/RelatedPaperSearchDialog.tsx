import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ProblemMapPaper, RelatedPaperSearchTurn } from "../../entities/problem-map/types";
import * as api from "./api";

interface Props {
  graphId: string;
  papers: ProblemMapPaper[];
  initialStudyId?: string;
  onClose: () => void;
}

interface SearchSessionConfig {
  studyIds: string[];
  model: string;
  ccfAOnly: boolean;
}

interface ContextStats {
  estimatedTokens: number;
  truncated: boolean;
}

export function RelatedPaperSearchDialog({ graphId, papers, initialStudyId, onClose }: Props) {
  const [selectedIds, setSelectedIds] = useState<string[]>(initialStudyId ? [initialStudyId] : []);
  const [model, setModel] = useState("");
  const [ccfAOnly, setCcfAOnly] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [turns, setTurns] = useState<RelatedPaperSearchTurn[]>([]);
  const [liveAssistant, setLiveAssistant] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [sessionConfig, setSessionConfig] = useState<SearchSessionConfig | null>(null);
  const [contextStats, setContextStats] = useState<ContextStats | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["llm", "settings"],
    queryFn: api.getLlmSettings,
  });

  useEffect(() => {
    if (!model && settingsQuery.data?.model) setModel(settingsQuery.data.model);
  }, [model, settingsQuery.data]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, liveAssistant, status]);

  useEffect(() => () => {
    if (requestIdRef.current) void api.cancelLlmRequest(requestIdRef.current);
    abortRef.current?.abort();
  }, []);

  const selectedPapers = useMemo(
    () => papers.filter((paper) => selectedIds.includes(paper.study_id)),
    [papers, selectedIds],
  );

  const togglePaper = (studyId: string) => {
    if (sessionConfig) return;
    setSelectedIds((current) =>
      current.includes(studyId) ? current.filter((id) => id !== studyId) : [...current, studyId],
    );
  };

  const close = () => {
    if (requestIdRef.current) void api.cancelLlmRequest(requestIdRef.current);
    abortRef.current?.abort();
    onClose();
  };

  const stop = async () => {
    const requestId = requestIdRef.current;
    if (requestId) {
      try {
        await api.cancelLlmRequest(requestId);
      } catch {
        // The local abort still stops rendering if the cancellation request fails.
      }
    }
    abortRef.current?.abort();
    setStatus("已停止，本次回答未加入对话历史。");
  };

  const resetSession = () => {
    if (streaming) return;
    setSessionConfig(null);
    setTurns([]);
    setLiveAssistant("");
    setStatus("");
    setError("");
    setContextStats(null);
  };

  const send = async () => {
    const content = prompt.trim();
    if (!content || !model || selectedIds.length === 0 || streaming) return;
    const priorTurns = [...turns];
    const activeConfig = sessionConfig ?? {
      studyIds: [...selectedIds],
      model,
      ccfAOnly,
    };
    if (!sessionConfig) setSessionConfig(activeConfig);
    setTurns((current) => [...current, { role: "user", content }]);
    setPrompt("");
    setLiveAssistant("");
    setError("");
    setStatus("正在建立所选论文上下文…");
    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;
    let answer = "";
    const outcome: { current: "pending" | "completed" | "failed" | "cancelled" } = {
      current: "pending",
    };
    try {
      await api.streamRelatedPaperSearch(
        graphId,
        {
          study_ids: activeConfig.studyIds,
          model: activeConfig.model,
          prompt: content,
          ccf_a_only: activeConfig.ccfAOnly,
          prior_turns: priorTurns,
        },
        (event, raw) => {
          const data = (raw ?? {}) as Record<string, unknown>;
          if (event === "request_created") requestIdRef.current = String(data.request_id ?? "");
          if (event === "context_built") {
            setContextStats({
              estimatedTokens: Number(data.estimated_input_tokens ?? 0),
              truncated: Boolean(data.truncated),
            });
          }
          if (event === "status") setStatus(String(data.message ?? ""));
          if (event === "delta") {
            answer += String(data.delta ?? "");
            setLiveAssistant(answer);
            setStatus("");
          }
          if (event === "completed") {
            const completed = String(data.content ?? answer);
            answer = completed;
            setTurns((current) => [...current, { role: "assistant", content: completed }]);
            setLiveAssistant("");
            setStatus("");
            outcome.current = "completed";
          }
          if (event === "failed") {
            outcome.current = "failed";
            setError(String(data.error_message ?? "搜索相关论文失败"));
            setStatus("");
          }
          if (event === "cancelled") {
            outcome.current = "cancelled";
            setStatus("已停止，本次回答未加入对话历史。");
          }
        },
        controller.signal,
      );
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "搜索相关论文失败");
      }
    } finally {
      if (outcome.current !== "completed") {
        setTurns(priorTurns);
        setPrompt(content);
        if (priorTurns.length === 0) setSessionConfig(null);
        setLiveAssistant("");
      }
      setStreaming(false);
      abortRef.current = null;
      requestIdRef.current = "";
    }
  };

  return (
    <div className="modal-backdrop app-dialog-backdrop pm-related-search-backdrop" role="presentation">
      <section className="app-dialog pm-related-search" role="dialog" aria-modal="true" aria-labelledby="related-paper-title">
        <header className="pm-related-search__header">
          <div>
            <span className="eyebrow">RELATED PAPER SEARCH</span>
            <h2 id="related-paper-title">搜索相关论文</h2>
            <p>把所选论文的暂定理解作为背景，由你亲自编写检索需求。</p>
          </div>
          <button type="button" className="btn btn--ghost" onClick={close}>关闭</button>
        </header>

        <div className="pm-related-search__body">
          <aside className="pm-related-search__context">
            <div className="pm-related-search__context-head">
              <strong>选择背景论文</strong>
              <small>已选 {selectedIds.length}/{papers.length}</small>
            </div>
            <p className="pm-muted">只携带研究场景、核心问题、主要方法，不携带论文全文或问题卡。</p>
            <div className="pm-related-search__papers">
              {papers.map((paper) => (
                <details key={paper.study_id} className="pm-related-search__paper" open={selectedIds.includes(paper.study_id)}>
                  <summary>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(paper.study_id)}
                      onChange={() => togglePaper(paper.study_id)}
                      onClick={(event) => event.stopPropagation()}
                      disabled={Boolean(sessionConfig)}
                    />
                    <span>{paper.title}</span>
                  </summary>
                  <dl>
                    <dt>研究场景</dt>
                    <dd>{paper.research_context || "尚未填写"}</dd>
                    <dt>核心问题</dt>
                    <dd>{paper.core_problem || "尚未填写"}</dd>
                    <dt>主要方法</dt>
                    <dd>{paper.main_approach || "尚未填写"}</dd>
                  </dl>
                </details>
              ))}
              {papers.length === 0 && <p className="pm-muted">当前问题地图还没有论文理解记录。</p>}
            </div>
          </aside>

          <main className="pm-related-search__chat">
            <div className="pm-related-search__messages">
              {turns.length === 0 && !liveAssistant && (
                <div className="pm-related-search__welcome">
                  <strong>检索需求由你决定</strong>
                  <p>例如：寻找同样处理长尾环境执行、但不采用冗余 rollout 的系统论文，并按方法差异分组。</p>
                </div>
              )}
              {turns.map((turn, index) => (
                <article key={`${turn.role}-${index}`} className={`pm-search-turn pm-search-turn--${turn.role}`}>
                  <strong>{turn.role === "user" ? "你" : "AI 检索助手"}</strong>
                  {turn.role === "assistant" ? (
                    <div className="markdown-body"><Markdown remarkPlugins={[remarkGfm]}>{turn.content}</Markdown></div>
                  ) : <p>{turn.content}</p>}
                </article>
              ))}
              {liveAssistant && (
                <article className="pm-search-turn pm-search-turn--assistant is-streaming">
                  <strong>AI 检索助手</strong>
                  <div className="markdown-body"><Markdown remarkPlugins={[remarkGfm]}>{liveAssistant}</Markdown></div>
                </article>
              )}
              {status && <p className="pm-related-search__status">{status}</p>}
              {error && <p className="error-text">{error}</p>}
              <div ref={chatEndRef} />
            </div>

            <div className="pm-related-search__composer">
              <div className="pm-related-search__options">
                <label>
                  模型
                  <select value={model} onChange={(event) => setModel(event.target.value)} disabled={streaming || Boolean(sessionConfig)}>
                    {settingsQuery.data && (
                      <>
                        <option value={settingsQuery.data.model}>DeepSeek V4 Flash（联网检索）</option>
                        <option value={settingsQuery.data.kimi_model}>Kimi K3（联网检索）</option>
                      </>
                    )}
                  </select>
                </label>
                <label className="pm-related-search__ccf">
                  <input
                    type="checkbox"
                    checked={ccfAOnly}
                    onChange={(event) => setCcfAOnly(event.target.checked)}
                    disabled={streaming || Boolean(sessionConfig)}
                  />
                  只筛选已发表于 CCF-A 类会议的论文
                </label>
              </div>
              {ccfAOnly && (
                <p className="pm-related-search__constraint">将要求模型逐篇给出会议、年份和 CCF 目录版本；无法核验的不进入正式推荐。</p>
              )}
              {sessionConfig && !streaming && (
                <p className="pm-related-search__constraint">
                  本会话已锁定背景论文、模型和筛选条件，以保证多轮语义一致。
                  <button type="button" className="btn btn--ghost" onClick={resetSession}>重新设置条件</button>
                </p>
              )}
              {contextStats && (
                <p className="pm-related-search__constraint">
                  本轮输入约 {contextStats.estimatedTokens.toLocaleString()} tokens
                  {contextStats.truncated ? "；已裁剪过长的论文理解或较早对话。" : "；未发生裁剪。"}
                </p>
              )}
              <div className="pm-related-search__input-row">
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") send();
                  }}
                  placeholder="填写你自己的检索需求；Ctrl/Cmd + Enter 发送…"
                  disabled={streaming}
                />
                {streaming ? (
                  <button type="button" className="btn btn--ghost" onClick={() => void stop()}>停止</button>
                ) : (
                  <button type="button" className="btn" onClick={send} disabled={!prompt.trim() || !model || selectedIds.length === 0}>
                    搜索并回答
                  </button>
                )}
              </div>
              {selectedPapers.length === 0 && <small className="error-text">请至少选择一篇背景论文。</small>}
            </div>
          </main>
        </div>
      </section>
    </div>
  );
}
