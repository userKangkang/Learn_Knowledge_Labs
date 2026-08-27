import { useState } from "react";
import type { PaperKnowledgeInquiry } from "../../../entities/paper-study/types";
import * as api from "../api";
import { PaperDialogue } from "./PaperDialogue";
import type { RunFn } from "./shared";

type Props = {
  studyId: string;
  textModel: string;
  busy: boolean;
  run: RunFn;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

export function PaperKnowledgeInquiryDialog({ studyId, textModel, busy, run, onClose, onSaved }: Props) {
  const [inquiry, setInquiry] = useState<PaperKnowledgeInquiry | null>(null);
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [summary, setSummary] = useState("");
  const [liveUser, setLiveUser] = useState("");
  const [liveAssistant, setLiveAssistant] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);

  const handleStreamEvent = (event: string, data: unknown) => {
    const payload = (data ?? {}) as { delta?: string; error_message?: string };
    if (event === "delta" && payload.delta) setLiveAssistant((value) => value + payload.delta);
    if (event === "failed") throw new Error(payload.error_message || "临时知识点对话失败");
  };

  const streamTurn = async (target: PaperKnowledgeInquiry, content: string) => {
    setQuestion("");
    setLiveUser(content);
    setLiveAssistant("");
    try {
      await api.streamKnowledgeInquiryMessage(studyId, target.id, content, textModel, handleStreamEvent);
      setInquiry(await api.getKnowledgeInquiry(studyId, target.id));
    } finally {
      setLiveUser("");
      setLiveAssistant("");
    }
  };

  const start = () => {
    const nextTitle = title.trim();
    const firstQuestion = question.trim();
    if (!nextTitle || !firstQuestion || !textModel) return;
    void run(async () => {
      const created = await api.createKnowledgeInquiry(studyId, nextTitle);
      setInquiry(created);
      await streamTurn(created, firstQuestion);
    });
  };

  const send = () => {
    const content = question.trim();
    if (!content) return Promise.resolve();
    if (!inquiry) {
      start();
      return Promise.resolve();
    }
    return run(() => streamTurn(inquiry, content));
  };

  const save = () => {
    if (!inquiry || !title.trim()) return;
    void run(async () => {
      await api.saveKnowledgeCard(studyId, inquiry.id, title.trim(), summary);
      await onSaved();
      onClose();
    });
  };

  const close = () => {
    if (!inquiry) {
      onClose();
      return;
    }
    if (!confirm("结束这次临时询问且不保存知识卡片？")) return;
    void run(async () => {
      await api.discardKnowledgeInquiry(studyId, inquiry.id);
      onClose();
    });
  };

  const messages = inquiry?.messages.map((message) => ({
    ...message,
    study_id: studyId,
    stage: "OVERVIEW" as const,
  })) ?? [];
  const hasAnswer = inquiry?.messages.some((message) => message.role === "ASSISTANT") ?? false;

  return (
    <div className="paper-source-preview-backdrop paper-knowledge-inquiry-backdrop" role="presentation">
      <section className="paper-knowledge-inquiry" role="dialog" aria-modal="true" aria-label="临时询问知识点">
        <header>
          <div>
            <span className="eyebrow">TEMPORARY KNOWLEDGE INQUIRY</span>
            <h3>临时询问知识点</h3>
            <p>这段对话只围绕一个知识点展开，不会拼接进“论文全貌”的主对话。</p>
          </div>
          <button className="btn btn--ghost" disabled={busy} onClick={close}>
            {inquiry ? "结束" : "关闭"}
          </button>
        </header>
        <div className={inquiry ? "paper-knowledge-inquiry__title" : "paper-knowledge-inquiry__title paper-knowledge-inquiry__title--draft"}>
          {inquiry ? (
            <>
              <strong>{inquiry.title}</strong>
              <span>独立会话</span>
            </>
          ) : (
            <label>
              知识点名称
              <input value={title} maxLength={255} onChange={(event) => setTitle(event.target.value)} placeholder="例如：MicroVM、注意力机制、梯度累积" />
            </label>
          )}
        </div>
        <PaperDialogue
          messages={messages}
          streamingUser={liveUser}
          streamingAssistant={liveAssistant}
          question={question}
          setQuestion={setQuestion}
          onSend={send}
          busy={busy}
          sendLabel={inquiry ? "继续对话" : "发送"}
          sendDisabled={!inquiry && (!title.trim() || !textModel)}
          emptyText={inquiry ? undefined : "这是一段独立的临时对话，请在下方输入你想了解的问题。"}
          placeholder={inquiry ? "继续追问这个知识点…" : "例如：它和传统 VM 的机制差异是什么？"}
          secondaryAction={hasAnswer && !showSaveForm ? { label: "保存为知识卡片", onClick: () => setShowSaveForm(true) } : undefined}
        />
        {showSaveForm && (
              <div className="paper-knowledge-inquiry__save">
                <h4>保存知识卡片</h4>
                <p>保存后会在当前知识图中创建一个 CONCEPT 节点，并保留论文引用位置。</p>
                <label className="paper-field">
                  节点标题
                  <input value={title} maxLength={255} onChange={(event) => setTitle(event.target.value)} />
                </label>
                <label className="paper-field">
                  知识点摘要（可选）
                  <textarea value={summary} maxLength={12000} onChange={(event) => setSummary(event.target.value)} placeholder="用自己的话写下目前的理解，也可以暂时留空。" />
                </label>
                <div className="paper-knowledge-inquiry__save-actions">
                  <button className="btn btn--ghost" disabled={busy} onClick={() => setShowSaveForm(false)}>继续询问</button>
                  <button className="btn" disabled={busy || !title.trim()} onClick={save}>创建知识节点</button>
                </div>
              </div>
        )}
      </section>
    </div>
  );
}
