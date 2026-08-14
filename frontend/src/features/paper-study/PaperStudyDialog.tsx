import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PaperConceptMap, PaperStudy } from "../../entities/paper-study/types";
import type { KnowledgeNode } from "../../entities/node/types";
import { listNodes } from "../graph-editor/api";
import * as api from "./api";
import { PaperConceptMapStage } from "./components/PaperConceptMapStage";
import { PaperOverviewStage } from "./components/PaperOverviewStage";
import { PaperProblemMapStage } from "./components/PaperProblemMapStage";
import { PaperVerificationStage } from "./components/PaperVerificationStage";
import type { RunFn, SaveCardFn } from "./components/shared";

type Props = {
  open: boolean;
  graphId: string;
  initialStudyId?: string;
  onClose: () => void;
};

export function PaperStudyDialog({ open, graphId, initialStudyId, onClose }: Props) {
  const queryClient = useQueryClient();
  const [studies, setStudies] = useState<PaperStudy[]>([]);
  const [study, setStudy] = useState<PaperStudy | null>(null);
  const [tab, setTab] = useState(1);
  const [title, setTitle] = useState("");
  const [renameTitle, setRenameTitle] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedCardId, setSelectedCardId] = useState("");
  const [conceptMap, setConceptMap] = useState<PaperConceptMap | null>(null);
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);

  const refresh = async (id = study?.id) => {
    if (!id) return;
    const next = await api.getStudy(id);
    setStudy(next);
    setStudies((all) => [next, ...all.filter((x) => x.id !== next.id)]);
  };
  const refreshGraph = async () => {
    await queryClient.invalidateQueries({ queryKey: ["graphs", graphId, "nodes"] });
  };

  useEffect(() => {
    if (!open) return;
    void api
      .listStudies(graphId)
      .then((all) => {
        setStudies(all);
        const target = initialStudyId ? all.find((item) => item.id === initialStudyId) ?? null : null;
        setStudy(target ?? all[0] ?? null);
      })
      .catch((e) => setError(e.message));
    void listNodes(graphId).then(setNodes);
  }, [open, graphId, initialStudyId]);

  useEffect(() => {
    if (!selectedCardId) {
      setConceptMap(null);
      return;
    }
    void api
      .getConceptMap(selectedCardId)
      .then(setConceptMap)
      .catch((e) => setError(e.message));
  }, [selectedCardId]);

  const selectedCard = useMemo(
    () => study?.problem_cards.find((card) => card.id === selectedCardId) ?? null,
    [study, selectedCardId],
  );

  if (!open) return null;

  const run: RunFn = async (task) => {
    setBusy(true);
    setError("");
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  const create = () =>
    run(async () => {
      const next = await api.createStudy(graphId, title.trim() || "未命名论文理解");
      setTitle("");
      setStudy(next);
      setStudies((all) => [next, ...all]);
      setTab(1);
    });
  const rename = () => {
    if (!study || !renameTitle.trim()) return;
    void run(async () => {
      const next = await api.updateStudy(study.id, renameTitle.trim());
      setStudy(next);
      setStudies((all) => all.map((item) => (item.id === next.id ? next : item)));
      setRenaming(false);
    });
  };
  const saveCard: SaveCardFn = (card, patch) =>
    run(async () => {
      await api.updateCard(card.id, patch);
      await refresh();
    });

  return (
    <div className="paper-study-backdrop" role="presentation">
      <section className="paper-study-dialog" role="dialog" aria-modal="true" aria-label="论文理解">
        <header>
          <div>
            <span className="eyebrow">PAPER UNDERSTANDING</span>
            <h2>论文问题理解</h2>
            <p>不是学习路线：先确认全貌，再选择一个问题，才铺开必要知识。</p>
          </div>
          <button className="btn btn--ghost" onClick={onClose}>
            关闭
          </button>
        </header>
        <aside className="paper-study-sidebar">
          <strong>论文理解记录</strong>
          {studies.map((item) => (
            <button
              className={item.id === study?.id ? "paper-study-list active" : "paper-study-list"}
              key={item.id}
              onClick={() => {
                setStudy(item);
                setRenaming(false);
                setSelectedCardId("");
                setTab(1);
              }}
            >
              {item.title}
            </button>
          ))}
          {study && (
            renaming ? (
              <div className="paper-study-rename">
                <input
                  autoFocus
                  value={renameTitle}
                  maxLength={255}
                  onChange={(e) => setRenameTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") rename();
                    if (e.key === "Escape") setRenaming(false);
                  }}
                  placeholder="论文理解标题"
                />
                <div>
                  <button className="btn" disabled={busy || !renameTitle.trim()} onClick={rename}>保存</button>
                  <button className="btn btn--ghost" disabled={busy} onClick={() => setRenaming(false)}>取消</button>
                </div>
              </div>
            ) : (
              <button
                className="btn btn--ghost paper-study-rename-trigger"
                disabled={busy}
                onClick={() => {
                  setRenameTitle(study.title);
                  setRenaming(true);
                }}
              >
                修改当前标题
              </button>
            )
          )}
          <div className="paper-study-create">
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="论文标题" />
            <button className="btn" disabled={busy} onClick={create}>
              新建
            </button>
          </div>
          {study && (
            <button
              className="btn btn--danger"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  if (!confirm("删除这条论文理解记录及其论文附件？")) return;
                  await api.deleteStudy(study.id);
                  const all = await api.listStudies(graphId);
                  setStudies(all);
                  setStudy(all[0] ?? null);
                  setRenaming(false);
                })
              }
            >
              删除当前记录
            </button>
          )}
        </aside>
        <main className={tab === 1 ? "paper-study-main paper-study-main--overview" : "paper-study-main"}>
          {!study ? (
            <div className="empty-state">新建一条论文理解记录，再上传论文开始。</div>
          ) : (
            <>
              <nav className="paper-study-steps">
                {[
                  [1, "1. 论文全貌"],
                  [2, "2. 问题地图"],
                  [3, "3. 最小解释图"],
                  [4, "4. 回到原文"],
                ].map(([value, label]) => (
                  <button key={value} className={tab === value ? "active" : ""} onClick={() => setTab(Number(value))}>
                    {label}
                  </button>
                ))}
              </nav>
              {error && <p className="error-text">{error}</p>}
              {tab === 1 && <PaperOverviewStage study={study} busy={busy} run={run} refresh={refresh} />}
              {tab === 2 && (
                <PaperProblemMapStage
                  study={study}
                  selectedCardId={selectedCardId}
                  setSelectedCardId={setSelectedCardId}
                  busy={busy}
                  run={run}
                  refresh={refresh}
                  saveCard={saveCard}
                />
              )}
              {tab === 3 && (
                <PaperConceptMapStage
                  graphId={graphId}
                  card={selectedCard}
                  map={conceptMap}
                  nodes={nodes}
                  busy={busy}
                  run={run}
                  setMap={setConceptMap}
                  refresh={refresh}
                  refreshGraph={refreshGraph}
                />
              )}
              {tab === 4 && <PaperVerificationStage card={selectedCard} busy={busy} saveCard={saveCard} />}
            </>
          )}
        </main>
      </section>
    </div>
  );
}
