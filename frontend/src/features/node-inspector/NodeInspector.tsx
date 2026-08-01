import { useEffect, useState } from "react";
import {
  NODE_TYPES,
  NODE_TYPE_LABELS,
  type KnowledgeNode,
  type NodeType,
} from "../../entities/node/types";
import { ApiError } from "../../shared/api/client";
import { SessionList } from "../conversations/SessionList";
import { SummaryPanel } from "../summaries/SummaryPanel";

interface Props {
  node: KnowledgeNode | null;
  onClose: () => void;
  onSave: (payload: { title: string; node_type: NodeType }) => Promise<void>;
  onDelete: () => Promise<void>;
}

export function NodeInspector({ node, onClose, onSave, onDelete }: Props) {
  const [title, setTitle] = useState("");
  const [nodeType, setNodeType] = useState<NodeType>("CONCEPT");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!node) return;
    setTitle(node.title);
    setNodeType(node.node_type);
    setError(null);
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
              await onSave({ title: title.trim(), node_type: nodeType });
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
