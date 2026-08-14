import { useEffect, useState } from "react";
import type { PaperProblemCard, PaperProblemCardCreate, PaperStudy } from "../../../entities/paper-study/types";
import * as api from "../api";
import { PaperDialogue } from "./PaperDialogue";
import { emptyProblemCard, splitLines, type RefreshFn, type RunFn, type SaveCardFn } from "./shared";

type Props = {
  study: PaperStudy;
  selectedCardId: string;
  setSelectedCardId: (id: string) => void;
  busy: boolean;
  run: RunFn;
  refresh: RefreshFn;
  saveCard: SaveCardFn;
};

export function PaperProblemMapStage({ study, selectedCardId, setSelectedCardId, busy, run, refresh, saveCard }: Props) {
  const [question, setQuestion] = useState("");
  const messages = study.messages.filter((message) => message.stage === "PROBLEM_MAP");
  const [showCardForm, setShowCardForm] = useState(false);
  const [cardDraft, setCardDraft] = useState<PaperProblemCardCreate>(emptyProblemCard);
  const [hintCollapsed, setHintCollapsed] = useState(false);
  const [liveUser, setLiveUser] = useState("");
  const [liveAssistant, setLiveAssistant] = useState("");

  const handleStreamEvent = (event: string, data: unknown) => {
    const payload = (data ?? {}) as { delta?: string; error_message?: string };
    if (event === "delta" && payload.delta) setLiveAssistant((value) => value + payload.delta);
    if (event === "failed") throw new Error(payload.error_message || "论文问题对话失败");
  };
  const start = () =>
    run(async () => {
      setLiveAssistant("");
      await api.streamConversationStart(study.id, "PROBLEM_MAP", handleStreamEvent);
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
        await api.streamConversationMessage(study.id, "PROBLEM_MAP", content, handleStreamEvent);
        await refresh();
      } finally {
        setLiveUser("");
        setLiveAssistant("");
      }
    });
  };
  const createCard = () =>
    run(async () => {
      await api.createProblemCard(study.id, cardDraft);
      setCardDraft(emptyProblemCard());
      setShowCardForm(false);
      await refresh();
    });

  return (
    <div className="paper-stage paper-stage--problem-map">
      <div className={hintCollapsed ? "paper-problem-hint collapsed" : "paper-problem-hint"}>
        <div>
          <h3>先讨论“具体有哪些问题”</h3>
          {!hintCollapsed && (
            <p>这段对话继承前一阶段的已确认理解和对话记录。你可以先问“原来的流程在哪几处出问题”、再追问成因与边界；问题卡由你在讨论后亲自填写。</p>
          )}
        </div>
        <button className="btn btn--ghost" type="button" onClick={() => setHintCollapsed((value) => !value)}>
          {hintCollapsed ? "展开提示" : "收起提示"}
        </button>
      </div>
      {study.overview.user_status !== "CONFIRMED" ? (
        <small>先回到「论文全貌」确认你的暂定理解。</small>
      ) : (
        <>
          {!messages.length && !liveAssistant && (
            <button className="btn" disabled={busy} onClick={start}>
              让 DeepSeek 从暂定理解开始讨论问题
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
              placeholder="例如：原来的全流程为什么会造成长尾？这是一个问题还是几个问题？"
              secondaryAction={
                messages.some((message) => message.role === "USER") ? { label: "填写问题卡", onClick: () => setShowCardForm(true) } : undefined
              }
            />
          )}
        </>
      )}
      {showCardForm && (
        <div className="paper-source-preview-backdrop" role="presentation">
          <section className="paper-overview-form" role="dialog" aria-modal="true" aria-label="填写问题卡">
            <header>
              <div>
                <span className="eyebrow">MY PROBLEM CARD</span>
                <h3>填写一张问题卡</h3>
                <p>请把刚才讨论出的一个问题用自己的话固定下来；可先填写核心内容，其他栏位之后继续修订。</p>
              </div>
              <button className="btn btn--ghost" onClick={() => setShowCardForm(false)}>
                关闭
              </button>
            </header>
            <div className="paper-overview-form__body">
              <label className="paper-field">
                问题标题
                <input
                  value={cardDraft.title}
                  onChange={(e) => setCardDraft({ ...cardDraft, title: e.target.value })}
                  placeholder="例如：长尾环境交互为什么阻塞训练批次？"
                />
              </label>
              <label className="paper-field">
                定性概述
                <textarea value={cardDraft.qualitative_overview} onChange={(e) => setCardDraft({ ...cardDraft, qualitative_overview: e.target.value })} />
              </label>
              <label className="paper-field">
                专业性解读
                <textarea
                  value={cardDraft.technical_interpretation}
                  onChange={(e) => setCardDraft({ ...cardDraft, technical_interpretation: e.target.value })}
                />
              </label>
              <label className="paper-field">
                论文明确说了（每行一条）
                <textarea
                  value={cardDraft.paper_claims.join("\n")}
                  onChange={(e) => setCardDraft({ ...cardDraft, paper_claims: splitLines(e.target.value) })}
                />
              </label>
              <label className="paper-field">
                论文没有说 / 范围边界（每行一条）
                <textarea
                  value={cardDraft.paper_not_said.join("\n")}
                  onChange={(e) => setCardDraft({ ...cardDraft, paper_not_said: splitLines(e.target.value) })}
                />
              </label>
              <label className="paper-field">
                建议回看原文的位置
                <textarea
                  value={cardDraft.verification_anchor}
                  onChange={(e) => setCardDraft({ ...cardDraft, verification_anchor: e.target.value })}
                />
              </label>
              <label className="paper-field">
                回看后要回答的问题
                <textarea
                  value={cardDraft.verification_prompt}
                  onChange={(e) => setCardDraft({ ...cardDraft, verification_prompt: e.target.value })}
                />
              </label>
            </div>
            <footer className="paper-overview-form__footer">
              <button className="btn" disabled={busy || !cardDraft.title.trim()} onClick={() => void createCard()}>
                保存这张问题卡
              </button>
            </footer>
          </section>
        </div>
      )}
      <div className="problem-card-grid">
        {study.problem_cards.map((card) => (
          <ProblemCardView
            key={card.id}
            card={card}
            selected={selectedCardId === card.id}
            busy={busy}
            saveCard={saveCard}
            onSelect={() => setSelectedCardId(card.id)}
            onDelete={() => {
              if (confirm(`删除问题卡“${card.title}”？此操作不可恢复。`)) {
                void run(async () => {
                  await api.deleteProblemCard(card.id);
                  if (selectedCardId === card.id) setSelectedCardId("");
                  await refresh();
                });
              }
            }}
          />
        ))}
      </div>
    </div>
  );
}

function ProblemCardView({
  card,
  selected,
  busy,
  saveCard,
  onSelect,
  onDelete,
}: {
  card: PaperProblemCard;
  selected: boolean;
  busy: boolean;
  saveCard: SaveCardFn;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <article className={selected ? "problem-card active" : "problem-card"}>
      <button className="problem-card__select" onClick={onSelect}>
        {card.title}
      </button>
      <button className="paper-card-delete" type="button" disabled={busy} onClick={onDelete}>
        删除
      </button>
      <p>{card.qualitative_overview}</p>
      <details>
        <summary>专业性解读与边界</summary>
        <p>{card.technical_interpretation}</p>
        <strong>论文明确说了</strong>
        <ul>{card.paper_claims.map((x) => <li key={x}>{x}</li>)}</ul>
        <strong>论文没有说</strong>
        <ul>{card.paper_not_said.map((x) => <li key={x}>{x}</li>)}</ul>
        <CardEditor card={card} busy={busy} saveCard={saveCard} />
      </details>
      <label>
        我为什么关心
        <textarea defaultValue={card.user_interest} onBlur={(e) => void saveCard(card, { user_interest: e.target.value })} />
      </label>
      <label>
        我具体卡在哪里
        <textarea defaultValue={card.user_stuck_point} onBlur={(e) => void saveCard(card, { user_stuck_point: e.target.value })} />
      </label>
      <button
        className="btn btn--ghost"
        onClick={() => {
          onSelect();
          void saveCard(card, { selected: true, status: "EXPLORING" });
        }}
      >
        形成问题卡片
      </button>
    </article>
  );
}

function CardEditor({ card, busy, saveCard }: { card: PaperProblemCard; busy: boolean; saveCard: SaveCardFn }) {
  const savedClaims = card.paper_claims.join("\n");
  const savedNotSaid = card.paper_not_said.join("\n");
  const [qualitative, setQualitative] = useState(card.qualitative_overview);
  const [technical, setTechnical] = useState(card.technical_interpretation);
  const [claims, setClaims] = useState(savedClaims);
  const [notSaid, setNotSaid] = useState(savedNotSaid);

  useEffect(() => {
    setQualitative(card.qualitative_overview);
    setTechnical(card.technical_interpretation);
    setClaims(savedClaims);
    setNotSaid(savedNotSaid);
  }, [card.id, card.qualitative_overview, card.technical_interpretation, savedClaims, savedNotSaid]);

  const dirty =
    qualitative !== card.qualitative_overview ||
    technical !== card.technical_interpretation ||
    claims !== savedClaims ||
    notSaid !== savedNotSaid;

  return (
    <div className="problem-card__editor">
      <div className="problem-card__editor-heading">
        <strong>修正这张问题卡</strong>
        {dirty && <span>有未保存修改</span>}
      </div>
      <label>
        定性概述
        <textarea value={qualitative} onChange={(e) => setQualitative(e.target.value)} />
      </label>
      <label>
        专业性解读
        <textarea value={technical} onChange={(e) => setTechnical(e.target.value)} />
      </label>
      <label>
        论文明确说了（每行一条）
        <textarea value={claims} onChange={(e) => setClaims(e.target.value)} />
      </label>
      <label>
        论文没有说（每行一条）
        <textarea value={notSaid} onChange={(e) => setNotSaid(e.target.value)} />
      </label>
      <button
        className="btn btn--ghost"
        disabled={busy || !dirty}
        onClick={() =>
          void saveCard(card, {
            qualitative_overview: qualitative,
            technical_interpretation: technical,
            paper_claims: splitLines(claims),
            paper_not_said: splitLines(notSaid),
          })
        }
      >
        保存卡片修正
      </button>
    </div>
  );
}
