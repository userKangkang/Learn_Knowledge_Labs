import { useEffect, useState } from "react";
import type { PaperStudy } from "../../../entities/paper-study/types";
import * as api from "../api";
import { PaperDialogue } from "./PaperDialogue";
import { overviewFields, type RefreshFn, type RunFn } from "./shared";

type Props = {
  study: PaperStudy;
  busy: boolean;
  run: RunFn;
  refresh: RefreshFn;
};

export function PaperOverviewStage({ study, busy, run, refresh }: Props) {
  const [overview, setOverview] = useState(study.overview);
  const [question, setQuestion] = useState("");
  const [sourcePreview, setSourcePreview] = useState<api.PaperSourceTextPreview | null>(null);
  const [materialsCollapsed, setMaterialsCollapsed] = useState(false);
  const [showOverviewForm, setShowOverviewForm] = useState(false);
  const [liveUser, setLiveUser] = useState("");
  const [liveAssistant, setLiveAssistant] = useState("");
  const messages = study.messages.filter((message) => message.stage === "OVERVIEW");
  const canConfirm = [...overviewFields.map(([key]) => overview[key]), overview.user_understanding].every((value) =>
    value.trim(),
  );

  useEffect(() => setOverview(study.overview), [study]);

  const upload = async (file?: File) => {
    if (!file) return;
    await api.uploadDocument(study.id, file);
    await refresh();
  };
  const handleStreamEvent = (event: string, data: unknown) => {
    const payload = (data ?? {}) as { delta?: string; error_message?: string };
    if (event === "delta" && payload.delta) setLiveAssistant((value) => value + payload.delta);
    if (event === "failed") throw new Error(payload.error_message || "论文对话失败");
  };
  const start = () =>
    run(async () => {
      setLiveAssistant("");
      await api.streamConversationStart(study.id, "OVERVIEW", handleStreamEvent);
      await refresh();
      setLiveAssistant("");
    });
  const send = () => {
    const content = question.trim();
    if (!content) return Promise.resolve();
    return run(async () => {
      setQuestion("");
      setLiveUser(content);
      setLiveAssistant("");
      try {
        await api.streamConversationMessage(study.id, "OVERVIEW", content, handleStreamEvent);
        await refresh();
      } finally {
        setLiveUser("");
        setLiveAssistant("");
      }
    });
  };

  return (
    <div className="paper-stage paper-stage--overview">
      <div className={materialsCollapsed ? "paper-overview-lead collapsed" : "paper-overview-lead"}>
        <div className="paper-overview-intro">
          <h3>先通过对话获得论文全貌</h3>
          {!materialsCollapsed && (
            <p>先让 AI 用通俗语言介绍，再持续追问、质疑和复述；不是从空白表单开始。对话足够后，再沉淀为可编辑草稿。</p>
          )}
        </div>
        <button className="btn btn--ghost paper-overview-toggle" type="button" onClick={() => setMaterialsCollapsed((value) => !value)}>
          {materialsCollapsed ? "展开材料" : "收起材料"}
        </button>
        {!materialsCollapsed &&
          (!study.document ? (
            <label className="paper-upload">
              上传论文 PDF/图片
              <input
                type="file"
                accept=".pdf,image/png,image/jpeg,image/webp"
                onChange={(e) => void run(() => upload(e.target.files?.[0]))}
              />
            </label>
          ) : (
            <div className="paper-document">
              <div>
                <strong>{study.document.filename}</strong>
                <span>
                  {study.document.source_text_char_count > 0
                    ? `已提取 ${study.document.source_text_char_count.toLocaleString()} 字原文文本`
                    : "未从 PDF 提取到文本"}
                </span>
              </div>
              <p className="paper-document__note">DeepSeek 默认直接携带 PDF 原文；请先预览核对。Kimi 不是事实层的必经环节。</p>
              <div className="paper-document__actions">
                {study.document.source_text_char_count > 0 && (
                  <button
                    className="btn btn--ghost"
                    disabled={busy}
                    onClick={() => run(async () => setSourcePreview(await api.getSourceTextPreview(study.id)))}
                  >
                    预览提取文字
                  </button>
                )}
                <button
                  className="btn btn--ghost"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api.analyzeDocument(study.id);
                      await refresh();
                    })
                  }
                >
                  可选：Kimi 详细解读
                </button>
              </div>
              {study.document.kimi_detailed_analysis && (
                <details>
                  <summary>查看 Kimi 辅助详细解读（不替代原文）</summary>
                  <pre>{study.document.kimi_detailed_analysis}</pre>
                </details>
              )}
            </div>
          ))}
      </div>
      {study.document && (study.document.source_text_char_count > 0 || study.document.kimi_detailed_analysis) && !messages.length && !liveAssistant && (
        <button className="btn" disabled={busy} onClick={start}>
          让 DeepSeek 直接基于论文原文开始介绍
        </button>
      )}
      {(messages.length > 0 || liveAssistant) && (
        <PaperDialogue
          messages={messages}
          streamingUser={liveUser}
          streamingAssistant={liveAssistant}
          question={question}
          setQuestion={setQuestion}
          onSend={send}
          busy={busy}
          placeholder="追问、质疑，或用自己的话复述给 AI 检验…"
          secondaryAction={
            messages.some((message) => message.role === "USER") ? { label: "填写理解", onClick: () => setShowOverviewForm(true) } : undefined
          }
        />
      )}
      {showOverviewForm && (
        <div className="paper-source-preview-backdrop" role="presentation">
          <section className="paper-overview-form" role="dialog" aria-modal="true" aria-label="填写我的暂定理解">
            <header>
              <div>
                <span className="eyebrow">MY PROVISIONAL UNDERSTANDING</span>
                <h3>填写我的暂定理解</h3>
                <p>请根据对话用自己的话组织这五项内容。AI 没有代写；填写后仍可以回来继续追问与修正。</p>
              </div>
              <button className="btn btn--ghost" onClick={() => setShowOverviewForm(false)}>
                关闭
              </button>
            </header>
            <div className="paper-overview-form__body">
              {overviewFields.map(([key, label]) => (
                <label className="paper-field" key={key}>
                  {label}
                  <textarea value={overview[key]} onChange={(e) => setOverview({ ...overview, [key]: e.target.value })} />
                </label>
              ))}
              <label className="paper-field">
                我的当前复述 / 补充
                <textarea
                  value={overview.user_understanding}
                  onChange={(e) => setOverview({ ...overview, user_understanding: e.target.value })}
                />
              </label>
            </div>
            <footer className="paper-overview-form__footer">
              <button
                className="btn btn--ghost"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await api.updateOverview(study.id, overview);
                    await refresh();
                  })
                }
              >
                保存我的填写
              </button>
              <button
                className="btn"
                disabled={busy || !canConfirm}
                onClick={() =>
                  run(async () => {
                    await api.updateOverview(study.id, { ...overview, user_status: "CONFIRMED" });
                    await refresh();
                    setShowOverviewForm(false);
                  })
                }
              >
                我确认：这是我的当前暂定理解
              </button>
            </footer>
          </section>
        </div>
      )}
      {sourcePreview && (
        <div className="paper-source-preview-backdrop" role="presentation">
          <section className="paper-source-preview" role="dialog" aria-modal="true" aria-label="PDF 提取文字预览">
            <header>
              <div>
                <span className="eyebrow">SOURCE TEXT PREVIEW</span>
                <h3>{sourcePreview.filename}</h3>
                <p>
                  {sourcePreview.character_count.toLocaleString()} 字。{sourcePreview.extraction_note}
                </p>
              </div>
              <button className="btn btn--ghost" onClick={() => setSourcePreview(null)}>
                关闭预览
              </button>
            </header>
            <pre>{sourcePreview.content}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
