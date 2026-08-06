import { useEffect, useState } from "react";
import type { PaperProblemCard } from "../../../entities/paper-study/types";
import type { SaveCardFn } from "./shared";

type Props = {
  card: PaperProblemCard | null;
  busy: boolean;
  saveCard: SaveCardFn;
};

export function PaperVerificationStage({ card, busy, saveCard }: Props) {
  const [answer, setAnswer] = useState(card?.verification_answer ?? "");

  useEffect(() => setAnswer(card?.verification_answer ?? ""), [card]);

  if (!card) return <div className="empty-state">先在「问题地图」选择一个问题卡。</div>;

  return (
    <div className="paper-stage">
      <h3>回到原文验证</h3>
      <p>这一关不由 AI 宣布完成。请回看原文锚点，用自己的话解释，再自己标记状态。</p>
      <article className="verification">
        <strong>回看位置：{card.verification_anchor || "请先生成问题地图"}</strong>
        <p>{card.verification_prompt}</p>
        <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="我的解释…" />
        <div className="paper-actions">
          <button className="btn btn--ghost" disabled={busy} onClick={() => void saveCard(card, { verification_answer: answer, verification_status: "PARTLY" })}>
            部分理解，继续
          </button>
          <button className="btn btn--ghost" disabled={busy} onClick={() => void saveCard(card, { verification_answer: answer, verification_status: "STILL_STUCK" })}>
            仍卡住
          </button>
          <button
            className="btn"
            disabled={busy || !answer.trim()}
            onClick={() => void saveCard(card, { verification_answer: answer, verification_status: "CAN_EXPLAIN", status: "VERIFIED" })}
          >
            我能解释这个问题
          </button>
        </div>
      </article>
      <p className="paper-loop-note">完成的是「这篇论文的一个问题理解切片」。论文阅读仍可继续：回到问题地图选择下一张卡。</p>
    </div>
  );
}
