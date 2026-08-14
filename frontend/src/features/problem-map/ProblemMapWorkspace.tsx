import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Background,
  ConnectionMode,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
  type NodeMouseHandler,
  type OnNodeDrag,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ApiError } from "../../shared/api/client";
import type {
  ProblemCardLink,
  ProblemLinkType,
  ProblemMapPaper,
  SharedProblem,
} from "../../entities/problem-map/types";
import * as api from "./api";
import { PaperNodeView, type PaperFlowNode } from "./PaperNode";
import { ProblemCardNodeView, type ProblemCardFlowNode } from "./ProblemCardNode";
import { ProblemNodeView, type ProblemFlowNode } from "./ProblemNode";
import { CardLinkEdge, HierarchyEdge, PaperCardEdge, type CardLinkFlowEdge, type HierarchyFlowEdge, type PaperCardFlowEdge } from "./ProblemMapEdge";
import { SuggestionPanel } from "./SuggestionPanel";
import { RelatedPaperSearchDialog } from "./RelatedPaperSearchDialog";

const nodeTypes = { problem: ProblemNodeView, paper: PaperNodeView, card: ProblemCardNodeView };
const edgeTypes = { hierarchy: HierarchyEdge, cardLink: CardLinkEdge, paperCard: PaperCardEdge };

type Selection =
  | { kind: "problem"; id: string }
  | { kind: "paper"; id: string }
  | { kind: "card"; id: string }
  | { kind: "edge"; id: string; edgeType: "hierarchy" | "cardLink" }
  | null;

type PositionMap = Record<string, { x: number; y: number }>;

function positionKey(entityType: "PAPER" | "CARD" | "PROBLEM", entityId: string) {
  return `${entityType}:${entityId}`;
}

function defaultPosition(entityType: "PAPER" | "CARD" | "PROBLEM", index: number) {
  if (entityType === "PAPER") return { x: 80 + index * 330, y: 40 };
  if (entityType === "CARD") return { x: 100 + index * 320, y: 270 };
  return { x: 140 + index * 290, y: 560 };
}

function problemPosition(
  stored: { x: number; y: number } | undefined,
  index: number,
  hasCardLayer: boolean,
) {
  if (!stored) return defaultPosition("PROBLEM", index);
  // 旧版只有“论文 → 共享问题”两层，持久化的问题坐标通常落在现在的问题卡层。
  // 渲染时把这些旧坐标下移；用户再次拖动后会按新坐标正常持久化。
  if (hasCardLayer && stored.y < 500) return { x: stored.x, y: stored.y + 300 };
  return stored;
}

interface Props {
  graphId: string;
  graphTitle: string;
  onOpenPaper: (studyId: string) => void;
}

export function ProblemMapWorkspace({ graphId, graphTitle, onOpenPaper }: Props) {
  const qc = useQueryClient();
  const [nodes, setNodes, onNodesChange] = useNodesState<ProblemFlowNode | PaperFlowNode | ProblemCardFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<HierarchyFlowEdge | CardLinkFlowEdge | PaperCardFlowEdge>([]);
  const [positions, setPositions] = useState<PositionMap>({});
  const [selection, setSelection] = useState<Selection>(null);
  const [notice, setNotice] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [suggestionOpen, setSuggestionOpen] = useState(false);
  const [relatedPaperSearchOpen, setRelatedPaperSearchOpen] = useState(false);
  const [cardLinkDraft, setCardLinkDraft] = useState<{ cardId: string; problemId: string } | null>(null);
  const positionTimers = useRef<Record<string, number>>({});

  const bundleQuery = useQuery({
    queryKey: ["graphs", graphId, "problem-map"],
    queryFn: () => api.getProblemMap(graphId),
  });
  const bundle = bundleQuery.data;

  const invalidate = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["graphs", graphId, "problem-map"] });
  }, [graphId, qc]);

  useEffect(() => {
    if (!bundle) return;
    setPositions((prev) => {
      const next = { ...prev };
      for (const item of bundle.positions) {
        next[positionKey(item.entity_type, item.entity_id)] = { x: item.position_x, y: item.position_y };
      }
      return next;
    });
  }, [bundle]);

  const cardByCardId = useMemo(() => {
    const map = new Map<string, { studyId: string; studyTitle: string; title: string; qualitativeOverview: string; selected: boolean }>();
    for (const paper of bundle?.papers ?? []) {
      for (const card of paper.cards) {
        map.set(card.id, {
          studyId: paper.study_id,
          studyTitle: paper.title,
          title: card.title,
          qualitativeOverview: card.qualitative_overview,
          selected: card.selected,
        });
      }
    }
    return map;
  }, [bundle]);

  const paperById = useMemo(
    () => new Map((bundle?.papers ?? []).map((paper) => [paper.study_id, paper])),
    [bundle],
  );
  const paperIds = useMemo(() => new Set(bundle?.papers.map((paper) => paper.study_id) ?? []), [bundle]);
  const cardIds = useMemo(() => new Set(cardByCardId.keys()), [cardByCardId]);
  const problemById = useMemo(
    () => new Map((bundle?.problems ?? []).map((problem) => [problem.id, problem])),
    [bundle],
  );

  const flowNodes = useMemo<Array<ProblemFlowNode | PaperFlowNode | ProblemCardFlowNode>>(() => {
    if (!bundle) return [];
    const targetedByEdge = new Set(bundle.edges.map((edge) => edge.target_problem_id));
    const problemNodes: ProblemFlowNode[] = bundle.problems.map((problem, index) => ({
      id: problem.id,
      type: "problem",
      position: problemPosition(
        positions[positionKey("PROBLEM", problem.id)],
        index,
        bundle.papers.some((paper) => paper.cards.length > 0),
      ),
      selected: selection?.kind === "problem" && selection.id === problem.id,
      data: {
        title: problem.title,
        description: problem.description,
        isRoot: !targetedByEdge.has(problem.id),
        coveragePaperCount: problem.coverage_paper_count,
        coverageCoreCount: problem.coverage_core_count,
        coverageTouchedCount: problem.coverage_touched_count,
      },
    }));
    const paperNodes: PaperFlowNode[] = bundle.papers.map((paper, index) => ({
      id: paper.study_id,
      type: "paper",
      position: positions[positionKey("PAPER", paper.study_id)] ?? defaultPosition("PAPER", index),
      selected: selection?.kind === "paper" && selection.id === paper.study_id,
      data: {
        title: paper.title,
        cardCount: paper.cards.length,
        cardTitles: paper.cards.map((card) => card.title),
      },
    }));
    let cardIndex = 0;
    const cardNodes: ProblemCardFlowNode[] = bundle.papers.flatMap((paper) =>
      paper.cards.map((card) => {
        const index = cardIndex++;
        return {
          id: card.id,
          type: "card" as const,
          position: positions[positionKey("CARD", card.id)] ?? defaultPosition("CARD", index),
          selected: selection?.kind === "card" && selection.id === card.id,
          data: {
            title: card.title,
            qualitativeOverview: card.qualitative_overview,
            paperTitle: paper.title,
            selectedAsCore: card.selected,
          },
        };
      }),
    );
    return [...paperNodes, ...cardNodes, ...problemNodes];
  }, [bundle, positions, selection]);

  const flowEdges = useMemo<Array<HierarchyFlowEdge | CardLinkFlowEdge | PaperCardFlowEdge>>(() => {
    if (!bundle) return [];
    const hierarchy: HierarchyFlowEdge[] = bundle.edges.map((edge) => ({
      id: edge.id,
      source: edge.source_problem_id,
      target: edge.target_problem_id,
      type: "hierarchy",
      markerEnd: { type: MarkerType.ArrowClosed },
      selected: selection?.kind === "edge" && selection.edgeType === "hierarchy" && selection.id === edge.id,
      data: { relationLabel: edge.relation_label },
    }));
    const paperCards: PaperCardFlowEdge[] = bundle.papers.flatMap((paper) =>
      paper.cards.map((card) => ({
        id: `paper-card:${card.id}`,
        source: paper.study_id,
        target: card.id,
        type: "paperCard" as const,
        markerEnd: { type: MarkerType.ArrowClosed },
        selectable: false,
        data: {},
      })),
    );
    const cardLinks: CardLinkFlowEdge[] = bundle.links.map((link) => {
      return {
        id: link.id,
        source: link.problem_card_id,
        target: link.shared_problem_id,
        type: "cardLink",
        markerEnd: { type: MarkerType.ArrowClosed },
        selected: selection?.kind === "edge" && selection.edgeType === "cardLink" && selection.id === link.id,
        data: { linkType: link.link_type },
      };
    });
    return [...paperCards, ...hierarchy, ...cardLinks];
  }, [bundle, selection]);

  useEffect(() => {
    setNodes(flowNodes);
  }, [flowNodes, setNodes]);

  useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  const createProblemMutation = useMutation({
    mutationFn: (payload: { title: string; description: string }) => api.createProblem(graphId, payload),
    onSuccess: async (problem) => {
      setSelection({ kind: "problem", id: problem.id });
      await invalidate();
    },
  });

  const updateProblemMutation = useMutation({
    mutationFn: ({ problemId, ...payload }: { problemId: string; title: string; description: string }) =>
      api.updateProblem(problemId, payload),
    onSuccess: async () => invalidate(),
  });

  const deleteProblemMutation = useMutation({
    mutationFn: (problemId: string) => api.deleteProblem(problemId),
    onSuccess: async () => {
      setSelection(null);
      await invalidate();
    },
  });

  const hierarchyMutation = useMutation({
    mutationFn: (payload: { source_problem_id: string; target_problem_id: string }) =>
      api.createProblemEdge(graphId, payload),
    onSuccess: async () => invalidate(),
  });

  const updateEdgeMutation = useMutation({
    mutationFn: ({ edgeId, ...payload }: { edgeId: string; relation_label?: string; reverse?: boolean }) =>
      api.updateProblemEdge(edgeId, payload),
    onSuccess: async () => invalidate(),
  });

  const deleteEdgeMutation = useMutation({
    mutationFn: (edgeId: string) => api.deleteProblemEdge(edgeId),
    onSuccess: async () => {
      setSelection(null);
      await invalidate();
    },
  });

  const linkMutation = useMutation({
    mutationFn: ({
      cardId,
      ...payload
    }: {
      cardId: string;
      shared_problem_id: string;
      link_type?: ProblemLinkType;
    }) => api.createCardLink(cardId, payload),
    onSuccess: async () => invalidate(),
  });

  const updateLinkMutation = useMutation({
    mutationFn: ({ linkId, ...payload }: { linkId: string; link_type: ProblemLinkType }) =>
      api.updateCardLink(linkId, payload),
    onSuccess: async () => invalidate(),
  });

  const deleteLinkMutation = useMutation({
    mutationFn: (linkId: string) => api.deleteCardLink(linkId),
    onSuccess: async () => invalidate(),
  });

  const runGuarded = useCallback(
    async (task: () => Promise<unknown>) => {
      setNotice("");
      try {
        await task();
      } catch (error) {
        setNotice(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "操作失败");
      }
    },
    [],
  );

  const persistPosition = useCallback(
    (entityType: "PAPER" | "CARD" | "PROBLEM", entityId: string, x: number, y: number) => {
      const key = positionKey(entityType, entityId);
      setPositions((prev) => ({ ...prev, [key]: { x, y } }));
      window.clearTimeout(positionTimers.current[key]);
      positionTimers.current[key] = window.setTimeout(() => {
        void api.savePositions(graphId, [{ entity_type: entityType, entity_id: entityId, position_x: x, position_y: y }]);
      }, 300);
    },
    [graphId],
  );

  const onNodeDragStop: OnNodeDrag = useCallback(
    (_event, node) => {
      const type = node.type === "paper" ? "PAPER" : node.type === "card" ? "CARD" : "PROBLEM";
      persistPosition(type, node.id, node.position.x, node.position.y);
    },
    [persistPosition],
  );

  const onNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    setSelection(
      node.type === "paper"
        ? { kind: "paper", id: node.id }
        : node.type === "card"
          ? { kind: "card", id: node.id }
          : { kind: "problem", id: node.id },
    );
  }, []);

  const onConnect = useCallback(
    (connection: Connection) => {
      const { source, target } = connection;
      if (!source || !target) return;
      const sourceIsPaper = paperIds.has(source);
      const targetIsPaper = paperIds.has(target);
      const sourceIsCard = cardIds.has(source);
      const targetIsCard = cardIds.has(target);
      if (sourceIsPaper && targetIsPaper) {
        setNotice("论文之间不能直接连线，请让它们指向同一个共享问题");
        return;
      }
      if (sourceIsCard || targetIsCard) {
        const cardId = sourceIsCard ? source : target;
        const problemId = sourceIsCard ? target : source;
        if (paperIds.has(problemId) || cardIds.has(problemId) || !problemById.has(problemId)) {
          setNotice("问题卡只能连接到共享问题；论文与问题卡的归属关系由系统维护");
          return;
        }
        setCardLinkDraft({ cardId, problemId });
        return;
      }
      if (!sourceIsPaper && !targetIsPaper && problemById.has(source) && problemById.has(target)) {
        setNotice("");
        hierarchyMutation.mutate({ source_problem_id: source, target_problem_id: target });
        return;
      }
      setNotice("请从论文的问题卡节点连接到共享问题节点");
    },
    [paperIds, cardIds, problemById, hierarchyMutation],
  );

  const addChildProblem = useCallback(
    (parent: SharedProblem, title: string, description: string) =>
      runGuarded(async () => {
        const child = await api.createProblem(graphId, { title, description });
        const parentPosition = positions[positionKey("PROBLEM", parent.id)] ?? { x: 140, y: 340 };
        await api.createProblemEdge(graphId, {
          source_problem_id: parent.id,
          target_problem_id: child.id,
        });
        setPositions((prev) => ({
          ...prev,
          [positionKey("PROBLEM", child.id)]: { x: parentPosition.x + 140, y: parentPosition.y + 180 },
        }));
        setSelection({ kind: "problem", id: child.id });
        await invalidate();
      }),
    [graphId, positions, invalidate, runGuarded],
  );

  const selectedProblem = selection?.kind === "problem" ? problemById.get(selection.id) ?? null : null;
  const selectedPaper = selection?.kind === "paper" ? paperById.get(selection.id) ?? null : null;
  const selectedCard = selection?.kind === "card" ? cardByCardId.get(selection.id) ?? null : null;

  const selectedHierarchyEdge =
    selection?.kind === "edge" && selection.edgeType === "hierarchy"
      ? bundle?.edges.find((edge) => edge.id === selection.id) ?? null
      : null;
  const selectedCardLink =
    selection?.kind === "edge" && selection.edgeType === "cardLink"
      ? bundle?.links.find((link) => link.id === selection.id) ?? null
      : null;

  const problemLinksFor = (problemId: string) =>
    (bundle?.links ?? [])
      .filter((link) => link.shared_problem_id === problemId)
      .map((link) => {
        const card = cardByCardId.get(link.problem_card_id);
        return { ...link, cardTitle: card?.title ?? "问题卡", studyId: card?.studyId ?? "", studyTitle: card?.studyTitle ?? "" };
      });

  const paperLinksFor = (paper: ProblemMapPaper) =>
    (bundle?.links ?? [])
      .filter((link) => cardByCardId.get(link.problem_card_id)?.studyId === paper.study_id)
      .map((link) => {
        const card = cardByCardId.get(link.problem_card_id);
        const problem = problemById.get(link.shared_problem_id);
        return {
          ...link,
          cardId: link.problem_card_id,
          cardTitle: card?.title ?? "问题卡",
          problemTitle: problem?.title ?? "未知问题",
        };
      });

  const cardLinksFor = (cardId: string) =>
    (bundle?.links ?? [])
      .filter((link) => link.problem_card_id === cardId)
      .map((link) => ({ ...link, problemTitle: problemById.get(link.shared_problem_id)?.title ?? "未知问题" }));

  return (
    <div className="pm-workspace">
      <header className="pm-topbar">
        <div className="pm-topbar__left">
          <Link to={`/graphs/${graphId}`} className="topbar__back">
            ← 知识图
          </Link>
          <h1>{graphTitle}</h1>
          <span className="eyebrow">论文-问题导图</span>
        </div>
        <div className="pm-topbar__tools">
          <span className="pm-hint">论文 → 问题卡 → 共享问题；问题拖向问题 = 建立细分关系</span>
          <button type="button" className="btn btn--ghost" onClick={() => setRelatedPaperSearchOpen(true)}>
            搜索相关论文
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setSuggestionOpen(true)}>
            提议关联
          </button>
          <button type="button" className="btn" onClick={() => setCreateOpen(true)}>
            新建问题
          </button>
        </div>
      </header>

      <div className="pm-body">
        <div className="pm-canvas-wrap">
          {bundleQuery.isLoading && <div className="pm-empty">加载导图…</div>}
          {bundle && bundle.papers.length === 0 && bundle.problems.length === 0 && (
            <div className="pm-empty">
              先在「论文理解」里建立问题卡，再回到这里把论文指向共享问题。
            </div>
          )}
          <ReactFlow<ProblemFlowNode | PaperFlowNode | ProblemCardFlowNode, HierarchyFlowEdge | CardLinkFlowEdge | PaperCardFlowEdge>
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={onNodeClick}
            onEdgeClick={(_event, edge) => {
              if (edge.type === "paperCard") return;
              setSelection({
                kind: "edge",
                id: edge.id,
                edgeType: edge.type === "hierarchy" ? "hierarchy" : "cardLink",
              });
            }}
            onPaneClick={() => setSelection(null)}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            connectionMode={ConnectionMode.Loose}
            fitView
            deleteKeyCode={null}
          >
            <Background gap={18} size={1} />
            <MiniMap />
            <Controls />
          </ReactFlow>
        </div>

        <aside className="pm-inspector">
          {selectedProblem && (
            <ProblemInspector
              problem={selectedProblem}
              links={problemLinksFor(selectedProblem.id)}
              busy={createProblemMutation.isPending || updateProblemMutation.isPending || deleteProblemMutation.isPending}
              onSave={(title, description) =>
                runGuarded(() => updateProblemMutation.mutateAsync({ problemId: selectedProblem.id, title, description }))
              }
              onDelete={() => runGuarded(() => deleteProblemMutation.mutateAsync(selectedProblem.id))}
              onAddChild={(title, description) => addChildProblem(selectedProblem, title, description)}
            />
          )}
          {selectedPaper && (
            <PaperInspector
              paper={selectedPaper}
              links={paperLinksFor(selectedPaper)}
              problems={bundle?.problems ?? []}
              busy={linkMutation.isPending || updateLinkMutation.isPending || deleteLinkMutation.isPending}
              onOpenPaper={() => onOpenPaper(selectedPaper.study_id)}
              onLink={(cardId, problemId, linkType) =>
                runGuarded(() => linkMutation.mutateAsync({ cardId, shared_problem_id: problemId, link_type: linkType }))
              }
              onUnlink={(linkId) => runGuarded(() => deleteLinkMutation.mutateAsync(linkId))}
            />
          )}
          {selectedCard && selection?.kind === "card" && (
            <ProblemCardInspector
              cardId={selection.id}
              card={selectedCard}
              links={cardLinksFor(selection.id)}
              problems={bundle?.problems ?? []}
              busy={linkMutation.isPending || updateLinkMutation.isPending || deleteLinkMutation.isPending}
              onOpenPaper={() => onOpenPaper(selectedCard.studyId)}
              onLink={(problemId, linkType) =>
                runGuarded(() => linkMutation.mutateAsync({ cardId: selection.id, shared_problem_id: problemId, link_type: linkType }))
              }
              onUnlink={(linkId) => runGuarded(() => deleteLinkMutation.mutateAsync(linkId))}
            />
          )}
          {selectedHierarchyEdge && (
            <HierarchyEdgeInspector
              edge={selectedHierarchyEdge}
              sourceTitle={problemById.get(selectedHierarchyEdge.source_problem_id)?.title ?? "未知问题"}
              targetTitle={problemById.get(selectedHierarchyEdge.target_problem_id)?.title ?? "未知问题"}
              busy={updateEdgeMutation.isPending}
              onSave={(relationLabel) =>
                runGuarded(() => updateEdgeMutation.mutateAsync({ edgeId: selectedHierarchyEdge.id, relation_label: relationLabel }))
              }
              onReverse={() => runGuarded(() => updateEdgeMutation.mutateAsync({ edgeId: selectedHierarchyEdge.id, reverse: true }))}
              onDelete={() => runGuarded(() => deleteEdgeMutation.mutateAsync(selectedHierarchyEdge.id))}
            />
          )}
          {selectedCardLink && (
            <CardLinkInspector
              link={selectedCardLink}
              card={cardByCardId.get(selectedCardLink.problem_card_id) ?? null}
              problemTitle={problemById.get(selectedCardLink.shared_problem_id)?.title ?? "未知问题"}
              busy={updateLinkMutation.isPending || deleteLinkMutation.isPending}
              onToggleLinkType={(linkType) =>
                runGuarded(() => updateLinkMutation.mutateAsync({ linkId: selectedCardLink.id, link_type: linkType }))
              }
              onDelete={() => runGuarded(() => deleteLinkMutation.mutateAsync(selectedCardLink.id))}
            />
          )}
          {!selectedProblem && !selectedPaper && !selectedCard && !selectedHierarchyEdge && !selectedCardLink && (
            <div className="pm-inspector__empty">
              选中节点或连线查看详情。
              <br />
              <br />
              覆盖度徽标显示的是"有几篇论文指向这个问题"（核心 / 提及分开统计）。
            </div>
          )}
        </aside>
      </div>

      {createOpen && (
        <CreateProblemDialog
          title="新建共享问题"
          confirmLabel="创建"
          onCancel={() => setCreateOpen(false)}
          onConfirm={(title, description) =>
            runGuarded(async () => {
              await createProblemMutation.mutateAsync({ title, description });
              setCreateOpen(false);
            })
          }
        />
      )}

      {relatedPaperSearchOpen && bundle && (
        <RelatedPaperSearchDialog
          graphId={graphId}
          papers={bundle.papers}
          initialStudyId={selectedPaper?.study_id ?? selectedCard?.studyId}
          onClose={() => setRelatedPaperSearchOpen(false)}
        />
      )}

      {cardLinkDraft && (
        <CardLinkDialog
          card={cardByCardId.get(cardLinkDraft.cardId) ?? null}
          problemTitle={problemById.get(cardLinkDraft.problemId)?.title ?? "未知问题"}
          onCancel={() => setCardLinkDraft(null)}
          onConfirm={(linkType) =>
            runGuarded(async () => {
              await linkMutation.mutateAsync({
                cardId: cardLinkDraft.cardId,
                shared_problem_id: cardLinkDraft.problemId,
                link_type: linkType,
              });
              setCardLinkDraft(null);
            })
          }
        />
      )}

      {suggestionOpen && (
        <SuggestionPanel
          graphId={graphId}
          cardByCardId={cardByCardId}
          problemById={problemById}
          existingLinks={bundle?.links ?? []}
          onClose={() => setSuggestionOpen(false)}
          onApplied={async (result) => {
            setSuggestionOpen(false);
            setNotice(
              `已创建 ${result.created_problems} 个问题、${result.created_edges} 条层级边、${result.created_links} 条关联`,
            );
            await invalidate();
          }}
        />
      )}

      {notice && (
        <div className="toast" onClick={() => setNotice("")} role="status">
          {notice}
        </div>
      )}
    </div>
  );
}

interface ProblemLinkRow extends ProblemCardLink {
  cardTitle: string;
  studyId: string;
  studyTitle: string;
}

function ProblemInspector({
  problem,
  links,
  busy,
  onSave,
  onDelete,
  onAddChild,
}: {
  problem: SharedProblem;
  links: ProblemLinkRow[];
  busy: boolean;
  onSave: (title: string, description: string) => void;
  onDelete: () => void;
  onAddChild: (title: string, description: string) => void;
}) {
  const [title, setTitle] = useState(problem.title);
  const [description, setDescription] = useState(problem.description);
  const [childTitle, setChildTitle] = useState("");
  const [childDescription, setChildDescription] = useState("");

  useEffect(() => {
    setTitle(problem.title);
    setDescription(problem.description);
  }, [problem]);

  return (
    <div className="pm-inspector__content">
      <span className="eyebrow">SHARED PROBLEM</span>
      <h3>共享问题</h3>
      <label className="paper-field">
        标题
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="paper-field">
        描述
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <div className="paper-actions">
        <button className="btn" disabled={busy || !title.trim()} onClick={() => onSave(title.trim(), description.trim())}>
          保存
        </button>
        <button className="btn btn--danger" disabled={busy} onClick={onDelete}>
          删除（需先解除关联）
        </button>
      </div>

      <div className="pm-inspector__section">
        <strong>覆盖度</strong>
        <p className="pm-coverage">
          {links.length
            ? `被 ${links.length} 张问题卡指向`
            : "还没有论文指向这个问题"}
        </p>
        <ul className="pm-link-list">
          {links.map((link) => (
            <li key={link.id}>
              <span className={`pm-link-type pm-link-type--${link.link_type.toLowerCase()}`}>
                {link.link_type === "CORE" ? "核心" : "提及"}
              </span>
              {link.studyTitle} · {link.cardTitle}
            </li>
          ))}
        </ul>
      </div>

      <div className="pm-inspector__section">
        <strong>添加子问题</strong>
        <label className="paper-field">
          子问题标题
          <input value={childTitle} onChange={(e) => setChildTitle(e.target.value)} placeholder="例如：在低资源场景下的…" />
        </label>
        <label className="paper-field">
          描述（可选）
          <textarea value={childDescription} onChange={(e) => setChildDescription(e.target.value)} />
        </label>
        <button
          className="btn btn--ghost"
          disabled={busy || !childTitle.trim()}
          onClick={() => onAddChild(childTitle.trim(), childDescription.trim())}
        >
          创建并连为子问题
        </button>
      </div>
    </div>
  );
}

interface PaperLinkRow extends ProblemCardLink {
  cardId: string;
  cardTitle: string;
  problemTitle: string;
}

interface CardProblemLinkRow extends ProblemCardLink {
  problemTitle: string;
}

function ProblemCardInspector({
  cardId,
  card,
  links,
  problems,
  busy,
  onOpenPaper,
  onLink,
  onUnlink,
}: {
  cardId: string;
  card: { studyTitle: string; title: string; qualitativeOverview: string; selected: boolean };
  links: CardProblemLinkRow[];
  problems: SharedProblem[];
  busy: boolean;
  onOpenPaper: () => void;
  onLink: (problemId: string, linkType: ProblemLinkType) => void;
  onUnlink: (linkId: string) => void;
}) {
  const [problemId, setProblemId] = useState(problems[0]?.id ?? "");
  const [linkType, setLinkType] = useState<ProblemLinkType>(card.selected ? "CORE" : "TOUCHED");

  useEffect(() => {
    setProblemId(problems[0]?.id ?? "");
    setLinkType(card.selected ? "CORE" : "TOUCHED");
  }, [cardId, card.selected, problems]);

  return (
    <div className="pm-inspector__content">
      <span className="eyebrow">PAPER PROBLEM CARD</span>
      <h3>{card.title}</h3>
      <p className="pm-muted">来源论文：{card.studyTitle}</p>
      <div className="pm-card-overview">
        <strong>定性概述</strong>
        <p>{card.qualitativeOverview || "尚未填写定性概述"}</p>
      </div>
      <button className="btn btn--ghost" onClick={onOpenPaper}>在论文理解中打开</button>

      <div className="pm-inspector__section">
        <strong>已关联的共享问题</strong>
        {!links.length && <p className="pm-muted">尚未关联共享问题。</p>}
        <ul className="pm-link-list">
          {links.map((link) => (
            <li key={link.id}>
              <span className={`pm-link-type pm-link-type--${link.link_type.toLowerCase()}`}>
                {link.link_type === "CORE" ? "核心" : "提及"}
              </span>
              {link.problemTitle}
              <button className="paper-card-delete" disabled={busy} onClick={() => onUnlink(link.id)}>解除</button>
            </li>
          ))}
        </ul>
      </div>

      <div className="pm-inspector__section">
        <strong>关联到共享问题</strong>
        <select value={problemId} onChange={(event) => setProblemId(event.target.value)} disabled={!problems.length}>
          <option value="">选择共享问题…</option>
          {problems.map((problem) => <option key={problem.id} value={problem.id}>{problem.title}</option>)}
        </select>
        <select value={linkType} onChange={(event) => setLinkType(event.target.value as ProblemLinkType)}>
          <option value="CORE">核心解决</option>
          <option value="TOUCHED">顺带提及</option>
        </select>
        <button className="btn" disabled={busy || !problemId} onClick={() => onLink(problemId, linkType)}>建立关联</button>
      </div>
    </div>
  );
}

function PaperInspector({
  paper,
  links,
  problems,
  busy,
  onOpenPaper,
  onLink,
  onUnlink,
}: {
  paper: ProblemMapPaper;
  links: PaperLinkRow[];
  problems: SharedProblem[];
  busy: boolean;
  onOpenPaper: () => void;
  onLink: (cardId: string, problemId: string, linkType: ProblemLinkType) => void;
  onUnlink: (linkId: string) => void;
}) {
  const [problemId, setProblemId] = useState(problems[0]?.id ?? "");
  const [linkType, setLinkType] = useState<ProblemLinkType>("TOUCHED");

  return (
    <div className="pm-inspector__content">
      <span className="eyebrow">PAPER</span>
      <h3>{paper.title}</h3>
      <button className="btn btn--ghost" onClick={onOpenPaper}>
        在论文理解中打开
      </button>

      <div className="pm-inspector__section">
        <strong>问题卡与关联</strong>
        {paper.cards.length === 0 && <p className="pm-muted">这篇论文还没有问题卡。</p>}
        {paper.cards.map((card) => {
          const cardLinks = links.filter((link) => link.cardId === card.id);
          return (
            <div key={card.id} className="pm-card-row">
              <div className="pm-card-row__title">
                {card.title}
                {card.selected && <span className="pm-link-type pm-link-type--core">核心</span>}
              </div>
              <ul className="pm-link-list">
                {cardLinks.map((link) => (
                  <li key={link.id}>
                    <span className={`pm-link-type pm-link-type--${link.link_type.toLowerCase()}`}>
                      {link.link_type === "CORE" ? "核心" : "提及"}
                    </span>
                    {link.problemTitle}
                    <button
                      className="paper-card-delete"
                      disabled={busy}
                      onClick={() => onUnlink(link.id)}
                      title="解除关联"
                    >
                      解除
                    </button>
                  </li>
                ))}
              </ul>
              <div className="pm-card-link-form">
                <select value={problemId} onChange={(e) => setProblemId(e.target.value)} disabled={!problems.length}>
                  <option value="">选择共享问题…</option>
                  {problems.map((problem) => (
                    <option key={problem.id} value={problem.id}>
                      {problem.title}
                    </option>
                  ))}
                </select>
                <select value={linkType} onChange={(e) => setLinkType(e.target.value as ProblemLinkType)}>
                  <option value="CORE">核心解决</option>
                  <option value="TOUCHED">顺带提及</option>
                </select>
                <button
                  className="btn btn--ghost"
                  disabled={busy || !problemId}
                  onClick={() => onLink(card.id, problemId, linkType)}
                >
                  关联
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HierarchyEdgeInspector({
  edge,
  sourceTitle,
  targetTitle,
  busy,
  onSave,
  onReverse,
  onDelete,
}: {
  edge: { relation_label: string };
  sourceTitle: string;
  targetTitle: string;
  busy: boolean;
  onSave: (relationLabel: string) => void;
  onReverse: () => void;
  onDelete: () => void;
}) {
  const [label, setLabel] = useState(edge.relation_label);
  useEffect(() => setLabel(edge.relation_label), [edge]);
  return (
    <div className="pm-inspector__content">
      <span className="eyebrow">HIERARCHY EDGE</span>
      <h3>细分关系</h3>
      <p className="pm-muted">
        {sourceTitle} → {targetTitle}
      </p>
      <label className="paper-field">
        关系标签
        <input value={label} onChange={(e) => setLabel(e.target.value)} />
      </label>
      <div className="paper-actions">
        <button className="btn" disabled={busy || !label.trim()} onClick={() => onSave(label.trim())}>
          保存标签
        </button>
        <button className="btn btn--ghost" disabled={busy} onClick={onReverse}>
          反转方向
        </button>
        <button className="btn btn--danger" disabled={busy} onClick={onDelete}>
          删除
        </button>
      </div>
    </div>
  );
}

function CardLinkInspector({
  link,
  card,
  problemTitle,
  busy,
  onToggleLinkType,
  onDelete,
}: {
  link: ProblemCardLink;
  card: { studyTitle: string; title: string } | null;
  problemTitle: string;
  busy: boolean;
  onToggleLinkType: (linkType: ProblemLinkType) => void;
  onDelete: () => void;
}) {
  return (
    <div className="pm-inspector__content">
      <span className="eyebrow">CARD LINK</span>
      <h3>问题卡 → 共享问题</h3>
      <p className="pm-muted">
        {card ? `${card.studyTitle} · ${card.title}` : "问题卡已删除"} → {problemTitle}
      </p>
      <div className="paper-actions">
        <button
          className={link.link_type === "CORE" ? "btn" : "btn btn--ghost"}
          disabled={busy}
          onClick={() => onToggleLinkType("CORE")}
        >
          核心解决
        </button>
        <button
          className={link.link_type === "TOUCHED" ? "btn" : "btn btn--ghost"}
          disabled={busy}
          onClick={() => onToggleLinkType("TOUCHED")}
        >
          顺带提及
        </button>
        <button className="btn btn--danger" disabled={busy} onClick={onDelete}>
          解除关联
        </button>
      </div>
    </div>
  );
}

function CreateProblemDialog({
  title,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  title: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: (title: string, description: string) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return (
    <div className="paper-source-preview-backdrop" role="presentation">
      <section className="paper-overview-form" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <div>
            <span className="eyebrow">PROBLEM MAP</span>
            <h3>{title}</h3>
          </div>
          <button className="btn btn--ghost" onClick={onCancel}>
            关闭
          </button>
        </header>
        <div className="paper-overview-form__body">
          <label className="paper-field">
            问题标题
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：长尾环境下模型训练效率" />
          </label>
          <label className="paper-field">
            描述（可选）
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
        </div>
        <footer className="paper-overview-form__footer">
          <button className="btn" disabled={!name.trim()} onClick={() => onConfirm(name.trim(), description.trim())}>
            {confirmLabel}
          </button>
        </footer>
      </section>
    </div>
  );
}

function CardLinkDialog({
  card,
  problemTitle,
  onCancel,
  onConfirm,
}: {
  card: { title: string; qualitativeOverview: string; selected: boolean } | null;
  problemTitle: string;
  onCancel: () => void;
  onConfirm: (linkType: ProblemLinkType) => void;
}) {
  const [linkType, setLinkType] = useState<ProblemLinkType>(card?.selected ? "CORE" : "TOUCHED");

  return (
    <div className="paper-source-preview-backdrop" role="presentation">
      <section className="paper-overview-form" role="dialog" aria-modal="true" aria-label="关联问题卡">
        <header>
          <div>
            <span className="eyebrow">CARD LINK</span>
            <h3>把问题卡指向「{problemTitle}」</h3>
            <p>问题卡：{card?.title ?? "问题卡已删除"}</p>
          </div>
          <button className="btn btn--ghost" onClick={onCancel}>
            取消
          </button>
        </header>
        <div className="paper-overview-form__body">
          {card?.qualitativeOverview && <p>{card.qualitativeOverview}</p>}
          <label className="paper-field">
            关联类型
            <select value={linkType} onChange={(e) => setLinkType(e.target.value as ProblemLinkType)}>
              <option value="CORE">核心解决</option>
              <option value="TOUCHED">顺带提及</option>
            </select>
          </label>
          <p className="pm-muted">深入问题卡默认按「核心解决」关联，仍可手动切换。</p>
        </div>
        <footer className="paper-overview-form__footer">
          <button className="btn" disabled={!card} onClick={() => onConfirm(linkType)}>
            建立关联
          </button>
        </footer>
      </section>
    </div>
  );
}

export function ProblemMapCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <ProblemMapWorkspace {...props} />
    </ReactFlowProvider>
  );
}
