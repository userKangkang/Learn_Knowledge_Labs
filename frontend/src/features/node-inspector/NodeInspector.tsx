import { useEffect, useState } from "react";
import {
  NODE_TYPES,
  NODE_TYPE_LABELS,
  type KnowledgeNode,
  type NodeType,
  type UnderstandingLevel,
} from "../../entities/node/types";
import { ApiError } from "../../shared/api/client";
import { SessionList } from "../conversations/SessionList";
import { SummaryPanel } from "../summaries/SummaryPanel";
import * as graphApi from "../graph-editor/api";

interface Props {
  node: KnowledgeNode | null;
  onClose: () => void;
  onSave: (payload: { title: string; node_type: NodeType; understanding_level: UnderstandingLevel }) => Promise<void>;
  onDelete: () => Promise<void>;
  onPaperReferenceAdded?: () => Promise<void>;
}

export function NodeInspector({ node, onClose, onSave, onDelete, onPaperReferenceAdded }: Props) {
  const [title, setTitle] = useState("");
  const [nodeType, setNodeType] = useState<NodeType>("CONCEPT");
  const [understandingLevel, setUnderstandingLevel] = useState<UnderstandingLevel>("NEEDS_WORK");
  const [paperStudies, setPaperStudies] = useState<Array<{ id: string; title: string; document: { id: string; filename: string } | null }>>([]);
  const [paperDocumentId, setPaperDocumentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!node) return;
    setTitle(node.title);
    setNodeType(node.node_type);
    setUnderstandingLevel(node.understanding_level);
    setPaperDocumentId("");
    setError(null);
    void graphApi.listPaperStudyOptions(node.graph_id).then(setPaperStudies).catch(() => setPaperStudies([]));
  }, [node]);

  if (!node) {
    return (
      <aside className="inspector">
        <p className="muted">选中节点可编辑标题、类型、摘要，并管理会话。</p>
      </aside>
    );
  }

  return (
    <aside className="inspector">
      <div className="inspector__header">
        <h2>节点详情</h2>
        <button type="button" className="btn btn--ghost" onClick={onClose}>
          关闭
        </button>
      </div>

      <label>
        标题
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="节点标题" />
      </label>

      <label>
        类型
        <select value={nodeType} onChange={(e) => setNodeType(e.target.value as NodeType)}>
          {NODE_TYPES.map((item) => (
            <option key={item} value={item}>
              {NODE_TYPE_LABELS[item]}
            </option>
          ))}
        </select>
      </label>

      <label>
        理解程度
        <select value={understandingLevel} onChange={(e) => setUnderstandingLevel(e.target.value as UnderstandingLevel)}>
          <option value="NEEDS_WORK">还需学习</option>
          <option value="BASIC">大致了解</option>
          <option value="DEEP">深度理解</option>
        </select>
      </label>

      <section className="inspector__slot">
        <div className="inspector__slot-head"><h3>关联论文</h3><span className="slot-badge">{node.paper_references.length} 篇</span></div>
        {node.paper_references.length ? <ul className="node-paper-reference-list">{node.paper_references.map((reference) => <li key={reference.id} title={reference.location || reference.filename}><strong>{reference.study_title}</strong><span>{reference.filename}</span>{reference.location && <small>{reference.location}</small>}</li>)}</ul> : <p className="muted" style={{ margin: 0, fontSize: 12 }}>尚未关联论文</p>}
        <select value={paperDocumentId} onChange={(e) => setPaperDocumentId(e.target.value)}>
          <option value="">选择论文后关联</option>
          {paperStudies.map((study) => {
            const document = study.document;
            if (!document) return null;
            return (
              <option key={document.id} value={document.id}>
                {study.title} · {document.filename}
              </option>
            );
          })}
        </select>
        <button type="button" className="btn btn--ghost" disabled={busy || !paperDocumentId} onClick={async () => { setBusy(true); setError(null); try { await graphApi.addNodePaperReference(node.id, { document_id: paperDocumentId }); setPaperDocumentId(""); await onPaperReferenceAdded?.(); } catch (err) { setError(err instanceof Error ? err.message : "关联论文失败"); } finally { setBusy(false); } }}>关联论文</button>
      </section>

      <SummaryPanel nodeId={node.id} graphId={node.graph_id} />
      <SessionList nodeId={node.id} />
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        上下文继承已归到每一场对话：打开对话后可在对话面板中配置。
      </p>

      {error && <p className="error-text">{error}</p>}

      <div className="inspector__actions">
        <button
          type="button"
          className="btn"
          disabled={busy || !title.trim()}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await onSave({ title: title.trim(), node_type: nodeType, understanding_level: understandingLevel });
            } catch (err) {
              setError(err instanceof Error ? err.message : "保存失败");
            } finally {
              setBusy(false);
            }
          }}
        >
          保存
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await onDelete();
            } catch (err) {
              if (err instanceof ApiError && err.code === "NODE_HAS_EDGES") {
                setError("该节点仍有边连接，请先删除相关边。");
              } else {
                setError(err instanceof Error ? err.message : "删除失败");
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          删除节点
        </button>
      </div>
    </aside>
  );
}
