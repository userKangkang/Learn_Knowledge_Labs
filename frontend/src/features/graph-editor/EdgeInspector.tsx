import { getEdgeDisplayLabel, type KnowledgeEdge } from "../../entities/edge/types";

interface Props {
  edge: KnowledgeEdge | null;
  sourceTitle?: string;
  targetTitle?: string;
  onClose: () => void;
  onChangeType: () => void;
  onReverse: () => Promise<void>;
  onDelete: () => Promise<void>;
}

export function EdgeInspector({
  edge,
  sourceTitle,
  targetTitle,
  onClose,
  onChangeType,
  onReverse,
  onDelete,
}: Props) {
  if (!edge) return null;

  const fromLabel = sourceTitle?.trim() || "起点";
  const toLabel = targetTitle?.trim() || "终点";

  return (
    <aside className="inspector">
      <div className="inspector__header">
        <h2>边详情</h2>
        <button type="button" className="btn btn--ghost" onClick={onClose}>
          关闭
        </button>
      </div>
      <label>
        当前关系
        <div className="inspector__value">{getEdgeDisplayLabel(edge.type, edge.custom_label)}</div>
      </label>
      <label>
        方向（父 → 子）
        <div className="inspector__value inspector__value--direction" title={`${fromLabel} → ${toLabel}`}>
          <span>{fromLabel}</span>
          <span className="muted">→</span>
          <span>{toLabel}</span>
        </div>
      </label>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        箭头起点是父节点，终点是子节点。若连反了可反转方向。
      </p>
      <div className="inspector__actions">
        <button type="button" className="btn" onClick={onChangeType}>
          更换类型
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => {
            void onReverse();
          }}
        >
          反转方向
        </button>
        <button
          type="button"
          className="btn btn--danger"
          onClick={() => {
            void onDelete();
          }}
        >
          删除边
        </button>
      </div>
    </aside>
  );
}
