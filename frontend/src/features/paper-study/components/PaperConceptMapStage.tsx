import { useEffect, useState } from "react";
import type { KnowledgeNode } from "../../../entities/node/types";
import type { PaperConceptMap, PaperProblemCard } from "../../../entities/paper-study/types";
import * as api from "../api";
import type { RefreshFn, RunFn } from "./shared";

type Props = {
  graphId: string;
  textModel: string;
  card: PaperProblemCard | null;
  map: PaperConceptMap | null;
  nodes: KnowledgeNode[];
  busy: boolean;
  run: RunFn;
  setMap: (map: PaperConceptMap | null) => void;
  refresh: RefreshFn;
  refreshGraph: () => Promise<void>;
};

export function PaperConceptMapStage({ card, textModel, map, nodes, busy, run, setMap, refresh, refreshGraph }: Props) {
  const currentMap = map?.workflow_stage === "EMPTY" ? null : map;
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

  useEffect(() => {
    if (currentMap?.workflow_stage === "REVIEW") {
      setSelectedKeys(
        currentMap.confirmed_candidate_keys.length
          ? currentMap.confirmed_candidate_keys
          : currentMap.candidate_review.filter((item) => item.graph_candidate === true).map((item) => String(item.key || "")),
      );
    }
  }, [currentMap]);

  if (!card) return <div className="empty-state">先在「问题地图」选择一个问题卡。</div>;

  const value = (item: Record<string, unknown>, key: string) => String(item[key] ?? "");
  const typeLabel: Record<string, string> = {
    MECHANISM: "基础机制",
    COMPONENT: "系统组件",
    PHENOMENON: "问题现象",
    EVIDENCE: "论文证据",
  };
  const generateLandscape = () =>
    run(async () => {
      const next = await api.generateConceptMap(card.id, textModel);
      setMap(next);
      await refresh();
    });
  const reviewCandidates = () =>
    run(async () => {
      const next = await api.reviewConceptMap(card.id, textModel);
      setMap(next);
      await refresh();
    });
  const finalize = () =>
    run(async () => {
      const next = await api.finalizeConceptMap(card.id, selectedKeys.filter(Boolean), textModel);
      setMap(next);
      await refresh();
    });

  return (
    <div className="paper-stage">
      <h3>{card.title} · 知识点审核与最小解释图</h3>
      {!currentMap && (
        <>
          <p>先让 AI 从问题卡和论文原文中铺开基础机制、系统组件、问题现象和论文证据。此步骤只生成可见候选，不会进入知识导图。</p>
          <button className="btn" disabled={busy || !textModel} onClick={generateLandscape}>
            第一步：展开问题相关知识点
          </button>
        </>
      )}
      {currentMap?.workflow_stage === "LANDSCAPE" && (
        <>
          <p>这是第一步的完整输出。请检查分类和解释，确认后才会请求第二步；论文方案与可迁移设计模式暂不纳入。</p>
          <div className="concept-landscape-grid">
            {currentMap.landscape_items.map((item, index) => (
              <article className="concept-landscape-card" key={String(item.key || index)}>
                <span className="concept-type">{typeLabel[String(item.type)] || String(item.type || "候选")}</span>
                <h4>{value(item, "title")}</h4>
                <p>{value(item, "qualitative_overview")}</p>
                <p>{value(item, "technical_interpretation")}</p>
                <small>因果作用：{value(item, "causal_role") || "未说明"}</small>
                <small>回看：{value(item, "paper_anchor") || "未标注"}</small>
              </article>
            ))}
          </div>
          <button className="btn" disabled={busy || !textModel} onClick={reviewCandidates}>
            我已检查第一步，确认并进入准入审核
          </button>
        </>
      )}
      {currentMap?.workflow_stage === "REVIEW" && (
        <>
          <p>这是第二步的审核输出。AI 只判断基础机制和系统组件是否值得进入知识导图；请逐项确认或取消，之后才生成重要程度。</p>
          <div className="concept-candidate-list">
            {currentMap.candidate_review.map((item, index) => {
              const key = value(item, "key");
              const checked = selectedKeys.includes(key);
              return (
                <label className="concept-candidate-card" key={key || index}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      setSelectedKeys((current) =>
                        event.target.checked ? [...new Set([...current, key])] : current.filter((itemKey) => itemKey !== key),
                      )
                    }
                  />
                  <div>
                    <span className="concept-type">{typeLabel[value(item, "type")] || value(item, "type")}</span>
                    <h4>{value(item, "title")}</h4>
                    <p>{value(item, "reason")}</p>
                    <small>可复用性：{value(item, "reusable_beyond_paper")}</small>
                    <small>需要解释：{value(item, "causal_explanation_need")}</small>
                  </div>
                </label>
              );
            })}
          </div>
          <button className="btn" disabled={busy || !textModel} onClick={finalize}>
            确认选中的节点并生成重要程度
          </button>
        </>
      )}
      {currentMap?.workflow_stage === "COMPLETED" && (
        <>
          <p>第三步已完成。只有用户确认的机制/组件进入了这里；MUST 是完成问题闭环的必要条件。关联知识节点仍需你手动确认。</p>
          <div className="concept-columns">
            {(["MUST", "ON_DEMAND", "EXTENSION"] as const).map((category) => (
              <section key={category}>
                <h4>{category === "MUST" ? "必须" : category === "ON_DEMAND" ? "建议" : "拓展"}</h4>
                {currentMap.items
                  .filter((item) => item.category === category)
                  .map((item) => (
                    <ConceptItem
                      key={item.id}
                      item={item}
                      nodes={nodes}
                      busy={busy}
                      run={run}
                      refresh={refresh}
                      setMap={setMap}
                      card={card}
                      refreshGraph={refreshGraph}
                    />
                  ))}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ConceptItem({
  item,
  nodes,
  busy,
  run,
  refresh,
  setMap,
  card,
  refreshGraph,
}: {
  item: PaperConceptMap["items"][number];
  nodes: KnowledgeNode[];
  busy: boolean;
  run: RunFn;
  refresh: RefreshFn;
  setMap: (map: PaperConceptMap | null) => void;
  card: PaperProblemCard;
  refreshGraph: () => Promise<void>;
}) {
  const [nodeId, setNodeId] = useState("");
  const reload = async () => {
    setMap(await api.getConceptMap(card.id));
    await refresh();
    await refreshGraph();
  };
  const statusLabel = item.user_status === "DEEP" ? "深度理解" : item.user_status === "BASIC" ? "大致了解" : "还需学习";

  return (
    <article className="concept-item">
      <strong>{item.title}</strong>
      <p>{item.explanation}</p>
      <small>回看：{item.paper_anchor || "未标注"}</small>
      <div className="concept-item__understanding">
        <button
          className={`btn btn--ghost ${item.user_status === "DEEP" ? "is-active" : ""}`}
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.updateConceptItem(item.id, "DEEP");
              await reload();
            })
          }
        >
          深度理解
        </button>
        <button
          className={`btn btn--ghost ${item.user_status === "BASIC" ? "is-active" : ""}`}
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.updateConceptItem(item.id, "BASIC");
              await reload();
            })
          }
        >
          大致了解
        </button>
        <button
          className={`btn btn--ghost ${item.user_status === "NEEDS_WORK" ? "is-active" : ""}`}
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.updateConceptItem(item.id, "NEEDS_WORK");
              await reload();
            })
          }
        >
          还需学习
        </button>
        <span className={`concept-status concept-status--${item.user_status.toLowerCase()}`}>当前阶段：{statusLabel}</span>
      </div>
      {item.graph_node_id ? (
        <small>已关联知识节点</small>
      ) : (
        <div className="concept-link">
          <select value={nodeId} onChange={(e) => setNodeId(e.target.value)}>
            <option value="">选择已有知识节点</option>
            {nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.title}
              </option>
            ))}
          </select>
          <button
            className="btn btn--ghost"
            disabled={busy || !nodeId}
            onClick={() =>
              run(async () => {
                await api.attachConceptNode(item.id, { existing_node_id: nodeId });
                await reload();
              })
            }
          >
            关联
          </button>
          <button
            className="btn btn--ghost"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api.attachConceptNode(item.id, { create_node: true });
                await reload();
              })
            }
          >
            手动确认后新建节点
          </button>
        </div>
      )}
    </article>
  );
}
