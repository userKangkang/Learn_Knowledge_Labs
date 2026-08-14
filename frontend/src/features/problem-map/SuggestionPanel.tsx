import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../shared/api/client";
import type {
  ProblemCardLink,
  ProblemMapApplyResult,
  ProblemMapSuggestionCardLink,
  ProblemMapSuggestionEdge,
  ProblemMapSuggestionProblem,
  SharedProblem,
} from "../../entities/problem-map/types";
import * as api from "./api";

interface CardInfo {
  studyId: string;
  studyTitle: string;
  title: string;
  selected: boolean;
}

interface DraftProblem extends ProblemMapSuggestionProblem {
  checked: boolean;
  titleDraft: string;
}

interface DraftEdge extends ProblemMapSuggestionEdge {
  checked: boolean;
}

interface DraftCardLink extends ProblemMapSuggestionCardLink {
  checked: boolean;
}

interface Draft {
  note: string;
  problems: DraftProblem[];
  edges: DraftEdge[];
  card_links: DraftCardLink[];
}

interface Props {
  graphId: string;
  cardByCardId: Map<string, CardInfo>;
  problemById: Map<string, SharedProblem>;
  existingLinks: ProblemCardLink[];
  onClose: () => void;
  onApplied: (result: ProblemMapApplyResult) => void;
}

export function SuggestionPanel({
  graphId,
  cardByCardId,
  problemById,
  existingLinks,
  onClose,
  onApplied,
}: Props) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [applying, setApplying] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    void api
      .suggestProblemMap(graphId)
      .then((response) => {
        setDraft({
          note: response.note,
          problems: response.problems.map((problem) => ({
            ...problem,
            checked: true,
            titleDraft: problem.title,
          })),
          edges: response.edges.map((edge) => ({ ...edge, checked: true })),
          card_links: response.card_links.map((link) => ({ ...link, checked: true })),
        });
      })
      .catch((error: unknown) => {
        setError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "提议失败");
      })
      .finally(() => setLoading(false));
  }, [graphId]);

  useEffect(load, [load]);

  const refTitle = (ref: string) =>
    problemById.get(ref)?.title ?? draft?.problems.find((problem) => problem.key === ref)?.title ?? ref;

  const refValid = (ref: string) =>
    problemById.has(ref) || Boolean(draft?.problems.find((problem) => problem.key === ref && problem.checked));

  const alreadyLinked = (link: ProblemMapSuggestionCardLink) =>
    problemById.has(link.problem_ref) &&
    existingLinks.some(
      (item) =>
        item.problem_card_id === link.problem_card_id && item.shared_problem_id === link.problem_ref,
    );

  const toggleProblem = (key: string) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            problems: current.problems.map((problem) =>
              problem.key === key ? { ...problem, checked: !problem.checked } : problem,
            ),
          }
        : current,
    );

  const setProblemTitle = (key: string, title: string) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            problems: current.problems.map((problem) =>
              problem.key === key ? { ...problem, titleDraft: title } : problem,
            ),
          }
        : current,
    );

  const toggleEdge = (index: number) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            edges: current.edges.map((edge, i) => (i === index ? { ...edge, checked: !edge.checked } : edge)),
          }
        : current,
    );

  const toggleCardLink = (index: number) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            card_links: current.card_links.map((link, i) =>
              i === index ? { ...link, checked: !link.checked } : link,
            ),
          }
        : current,
    );

  const handleApply = async () => {
    if (!draft) return;
    setApplying(true);
    setError("");
    try {
      const result = await api.applyProblemMap(graphId, {
        problems: draft.problems
          .filter((problem) => problem.checked)
          .map((problem) => ({
            key: problem.key,
            title: problem.titleDraft.trim() || problem.title,
            description: problem.description,
          })),
        edges: draft.edges
          .filter((edge) => edge.checked)
          .map((edge) => ({
            source_ref: edge.source_ref,
            target_ref: edge.target_ref,
            relation_label: edge.relation_label,
          })),
        card_links: draft.card_links
          .filter((link) => link.checked)
          .map((link) => ({
            problem_card_id: link.problem_card_id,
            problem_ref: link.problem_ref,
            link_type: link.link_type,
          })),
      });
      onApplied(result);
    } catch (error: unknown) {
      setError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "应用失败");
    } finally {
      setApplying(false);
    }
  };

  const selectedCount =
    (draft?.problems.filter((problem) => problem.checked).length ?? 0) +
    (draft?.edges.filter((edge) => edge.checked).length ?? 0) +
    (draft?.card_links.filter((link) => link.checked).length ?? 0);

  return (
    <div className="paper-source-preview-backdrop" role="presentation">
      <section className="paper-overview-form pm-suggestion" role="dialog" aria-modal="true" aria-label="提议关联">
        <header>
          <div>
            <span className="eyebrow">AI SUGGESTIONS</span>
            <h3>让模型提议共享问题与关联</h3>
            <p>模型只负责提议，不写入任何数据；勾选并确认后才会真正建节点和边。</p>
          </div>
          <button className="btn btn--ghost" onClick={onClose} disabled={applying}>
            关闭
          </button>
        </header>
        <div className="paper-overview-form__body">
          {loading && <p className="pm-muted">模型正在阅读问题卡并提议共享问题…</p>}
          {!loading && error && (
            <div className="pm-suggestion__error">
              <p className="error-text">{error}</p>
              <button className="btn btn--ghost" onClick={load}>
                重试
              </button>
            </div>
          )}
          {!loading && !error && draft && (
            <>
              {draft.note && <p className="pm-muted">{draft.note}</p>}

              <div className="pm-inspector__section">
                <strong>建议新建的共享问题（{draft.problems.length}）</strong>
                {draft.problems.length === 0 && <p className="pm-muted">模型没有建议新建问题。</p>}
                {draft.problems.map((problem) => (
                  <label key={problem.key} className="pm-suggestion__row">
                    <input
                      type="checkbox"
                      checked={problem.checked}
                      onChange={() => toggleProblem(problem.key)}
                    />
                    <span className="pm-suggestion__body">
                      <input
                        type="text"
                        value={problem.titleDraft}
                        onChange={(e) => setProblemTitle(problem.key, e.target.value)}
                        disabled={!problem.checked}
                      />
                      {problem.description && <small>{problem.description}</small>}
                      {problem.parent_key && (
                        <small className="pm-muted">挂在：{refTitle(problem.parent_key)}</small>
                      )}
                    </span>
                  </label>
                ))}
              </div>

              <div className="pm-inspector__section">
                <strong>建议的细分边（{draft.edges.length}）</strong>
                {draft.edges.length === 0 && <p className="pm-muted">模型没有建议层级边。</p>}
                {draft.edges.map((edge, index) => {
                  const valid = refValid(edge.source_ref) && refValid(edge.target_ref);
                  return (
                    <label key={`${edge.source_ref}-${edge.target_ref}-${index}`} className="pm-suggestion__row">
                      <input
                        type="checkbox"
                        checked={edge.checked}
                        disabled={!valid}
                        onChange={() => toggleEdge(index)}
                      />
                      <span className="pm-suggestion__body">
                        {refTitle(edge.source_ref)} → {refTitle(edge.target_ref)}
                        <small>
                          {edge.relation_label === "SPECIALIZES_INTO" ? "细分" : edge.relation_label}
                          {!valid && "（引用了未选中的问题）"}
                        </small>
                      </span>
                    </label>
                  );
                })}
              </div>

              <div className="pm-inspector__section">
                <strong>建议的问题卡关联（{draft.card_links.length}）</strong>
                {draft.card_links.length === 0 && <p className="pm-muted">模型没有建议关联。</p>}
                {draft.card_links.map((link, index) => {
                  const card = cardByCardId.get(link.problem_card_id);
                  const linked = alreadyLinked(link);
                  const valid = refValid(link.problem_ref) && !linked;
                  return (
                    <label key={`${link.problem_card_id}-${link.problem_ref}-${index}`} className="pm-suggestion__row">
                      <input
                        type="checkbox"
                        checked={link.checked}
                        disabled={!valid}
                        onChange={() => toggleCardLink(index)}
                      />
                      <span className="pm-suggestion__body">
                        {card?.studyTitle ?? "未知论文"} · {card?.title ?? "未知问题卡"} →{" "}
                        {refTitle(link.problem_ref)}
                        <small>
                          {link.link_type === "CORE" ? "核心解决" : "顺带提及"}
                          {linked && "（已关联）"}
                          {!valid && !linked && "（引用了未选中的问题）"}
                        </small>
                      </span>
                    </label>
                  );
                })}
              </div>
            </>
          )}
        </div>
        <footer className="paper-overview-form__footer">
          <span className="pm-muted">已选 {selectedCount} 项</span>
          <button className="btn" disabled={!draft || loading || applying || selectedCount === 0} onClick={handleApply}>
            {applying ? "应用中…" : "应用选中项"}
          </button>
        </footer>
      </section>
    </div>
  );
}
